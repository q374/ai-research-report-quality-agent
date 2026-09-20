"""证据校验影子结果查询与零费用重放接口。"""

from __future__ import annotations

import copy
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.gateway.authz import require_permission
from app.gateway.deps import (
    get_current_user,
    get_evidence_validation_repo,
    get_evidence_validation_service,
    get_run_store,
)

router = APIRouter(prefix="/api/threads", tags=["evidence-validation"])


class ResearchBriefRequest(BaseModel):
    task_id: str
    required_dimensions: list[str]
    allowed_domains: list[str]
    time_scope: str
    max_searches: int = Field(ge=0)
    max_pages: int = Field(ge=0)
    max_chars: int = Field(ge=0)
    forbidden_tools: list[str]


class EvidenceValidationReplayRequest(BaseModel):
    quality_profile_id: str
    brief: ResearchBriefRequest


class EvidenceReviewRequest(BaseModel):
    decision: Literal["approved", "returned", "rejected"]
    expected_report_hash: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason: str | None = None


def _not_found(run_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Run {run_id} not found")


async def _current_user_id(request: Request) -> str | None:
    auth = getattr(request.state, "auth", None)
    user = getattr(auth, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return str(user.id)
    return await get_current_user(request)


async def _owned_run(request: Request, thread_id: str, run_id: str) -> tuple[dict, str]:
    user_id = await _current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    run = await get_run_store(request).get(run_id, user_id=user_id)
    if run is None or run.get("thread_id") != thread_id:
        raise _not_found(run_id)
    return run, user_id


def _with_final_status(record: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    final_status = result.get("final_status") or result.get("auto_status")
    validation_result = result.get("validation_result")
    if isinstance(validation_result, dict) and isinstance(final_status, str):
        validation_result["status"] = final_status
    result["final_status"] = final_status
    result.setdefault("review_decisions", [])
    return result


@router.get("/{thread_id}/runs/{run_id}/evidence-validation")
@require_permission("runs", "read", owner_check=True)
async def get_evidence_validation(
    thread_id: str,
    run_id: str,
    request: Request,
) -> dict[str, Any]:
    _, user_id = await _owned_run(request, thread_id, run_id)
    record = await get_evidence_validation_repo(request).get_by_run(
        thread_id,
        run_id,
        user_id=user_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence validation not found")
    return _with_final_status(record)


@router.post("/{thread_id}/runs/{run_id}/evidence-validation/reviews")
@require_permission("threads", "write", owner_check=True, require_existing=True)
async def submit_evidence_review(
    thread_id: str,
    run_id: str,
    body: EvidenceReviewRequest,
    request: Request,
) -> dict[str, Any]:
    _, user_id = await _owned_run(request, thread_id, run_id)
    repository = get_evidence_validation_repo(request)
    record = await repository.get_by_run(
        thread_id,
        run_id,
        user_id=user_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence validation not found")
    try:
        updated = await repository.submit_review(
            validation_id=record["validation_id"],
            user_id=user_id,
            decision=body.decision,
            expected_report_hash=body.expected_report_hash,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Evidence validation not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Evidence review is not allowed") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _with_final_status(updated)


@router.post("/{thread_id}/runs/{run_id}/evidence-validation/replay")
@require_permission("threads", "write", owner_check=True, require_existing=True)
async def replay_evidence_validation(
    thread_id: str,
    run_id: str,
    body: EvidenceValidationReplayRequest,
    request: Request,
) -> dict[str, Any]:
    run, user_id = await _owned_run(request, thread_id, run_id)
    if run.get("status") != "success":
        raise HTTPException(status_code=409, detail="Only successful runs can be replayed")

    service = get_evidence_validation_service(request)
    eligibility = service.eligibility(
        user_id=user_id,
        quality_profile_id=body.quality_profile_id,
    )
    if eligibility == "user_not_allowed":
        raise HTTPException(status_code=403, detail="Current user is not enabled for evidence validation")
    if eligibility != "allowed":
        raise HTTPException(status_code=409, detail="Evidence validation profile is not enabled")

    try:
        record = await service.process_run(
            thread_id=thread_id,
            run_id=run_id,
            owner_user_id=user_id,
            quality_profile_id=body.quality_profile_id,
            brief=body.brief.model_dump(),
            source="manual_replay",
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Evidence validation is not allowed") from exc
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=409, detail="Evidence validation replay was rejected") from exc
    if record is None:
        raise HTTPException(status_code=409, detail="Evidence validation replay was skipped")
    return record
