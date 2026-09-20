"""证据校验查询与零费用重放 API 测试。"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from _router_auth_helpers import make_authed_test_app
from fastapi.testclient import TestClient

from app.gateway.auth.models import User
from app.gateway.routers import evidence_validation
from deerflow.config.evidence_validation_config import EvidenceValidationConfig

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


def _user(user_id: str) -> User:
    return User(
        email=f"{user_id[:4]}@example.com",
        password_hash="x",
        system_role="user",
        id=UUID(user_id),
    )


def valid_brief() -> dict:
    return {
        "task_id": "T001",
        "required_dimensions": [],
        "allowed_domains": ["example.com"],
        "time_scope": "current",
        "max_searches": 5,
        "max_pages": 5,
        "max_chars": 1000,
        "forbidden_tools": [],
    }


def validation_record() -> dict:
    return {
        "validation_id": "v1",
        "schema_version": "1.0",
        "user_id": USER_A,
        "thread_id": "t-a",
        "run_id": "r-a",
        "message_id": "m-a",
        "quality_profile_id": "evidence-research-v1",
        "report_hash": "hash-a",
        "source_payload": {
            "brief": valid_brief(),
            "claims": [],
            "evidence": [],
            "report": {"rendered_text": "回答"},
            "audit": {"source": "manual_replay"},
        },
        "validation_result": {"status": "review_required", "findings": []},
        "auto_status": "review_required",
        "semantic_evaluation": "not_evaluable",
        "created_at": "2026-09-19T00:00:00+00:00",
        "updated_at": "2026-09-19T00:00:00+00:00",
    }


def _make_client(
    *,
    user_id: str = USER_A,
    run: dict | None = None,
    stored: dict | None = None,
    config: EvidenceValidationConfig | None = None,
):
    app = make_authed_test_app(user_factory=lambda: _user(user_id))
    app.include_router(evidence_validation.router)

    run_store = MagicMock()
    run_store.get = AsyncMock(return_value=run)
    repo = MagicMock()
    repo.get_by_run = AsyncMock(return_value=stored)
    repo.submit_review = AsyncMock(return_value=stored)
    service = MagicMock()
    service.eligibility = MagicMock(return_value="allowed")
    service.process_run = AsyncMock(return_value=deepcopy(validation_record()))
    if config is not None:
        service.eligibility.side_effect = lambda *, user_id, quality_profile_id: (
            "allowed" if config.is_allowed(user_id=user_id, quality_profile_id=quality_profile_id) else ("user_not_allowed" if user_id not in config.allowed_user_ids else "profile_not_allowed")
        )

    app.state.run_store = run_store
    app.state.evidence_validation_repo = repo
    app.state.evidence_validation_service = service
    return TestClient(app), run_store, repo, service


def _run(*, user_id: str = USER_A, status: str = "success", thread_id: str = "t-a") -> dict:
    return {
        "run_id": "r-a",
        "thread_id": thread_id,
        "user_id": user_id,
        "status": status,
    }


def test_other_owner_gets_404():
    client, run_store, _, _ = _make_client(user_id=USER_B, run=None)
    with client:
        response = client.get("/api/threads/t-a/runs/r-a/evidence-validation")

    assert response.status_code == 404
    run_store.get.assert_awaited_once_with("r-a", user_id=USER_B)


def test_get_returns_404_when_validation_not_generated():
    client, _, _, _ = _make_client(run=_run(), stored=None)
    with client:
        response = client.get("/api/threads/t-a/runs/r-a/evidence-validation")
    assert response.status_code == 404


def test_get_exposes_manual_final_status_in_validation_result():
    stored = validation_record()
    stored["final_status"] = "confirmed"
    stored["review_decisions"] = [
        {
            "decision": "approved",
            "reviewer_user_id": USER_A,
            "report_hash": stored["report_hash"],
        }
    ]
    client, _, _, _ = _make_client(run=_run(), stored=stored)

    with client:
        response = client.get("/api/threads/t-a/runs/r-a/evidence-validation")

    assert response.status_code == 200
    assert response.json()["validation_result"]["status"] == "confirmed"
    assert response.json()["final_status"] == "confirmed"
    assert response.json()["review_decisions"][0]["decision"] == "approved"


def test_thread_run_mismatch_returns_404():
    client, _, _, _ = _make_client(run=_run(thread_id="other"), stored=validation_record())
    with client:
        response = client.get("/api/threads/t-a/runs/r-a/evidence-validation")
    assert response.status_code == 404


def test_manual_replay_is_idempotent():
    client, _, _, service = _make_client(run=_run())
    request = {"quality_profile_id": "evidence-research-v1", "brief": valid_brief()}
    with client:
        first = client.post("/api/threads/t-a/runs/r-a/evidence-validation/replay", json=request)
        second = client.post("/api/threads/t-a/runs/r-a/evidence-validation/replay", json=request)

    assert first.status_code == second.status_code == 200
    assert first.json()["validation_id"] == second.json()["validation_id"]
    assert service.process_run.await_count == 2


def test_manual_replay_rejects_non_success_run():
    client, _, _, service = _make_client(run=_run(status="running"))
    with client:
        response = client.post(
            "/api/threads/t-a/runs/r-a/evidence-validation/replay",
            json={"quality_profile_id": "evidence-research-v1", "brief": valid_brief()},
        )
    assert response.status_code == 409
    assert service.process_run.await_count == 0


def test_manual_replay_rejects_non_allowed_user_with_403():
    config = EvidenceValidationConfig(
        enabled=True,
        quality_profile_ids=["evidence-research-v1"],
        allowed_user_ids=[USER_B],
    )
    client, _, _, service = _make_client(run=_run(), config=config)
    with client:
        response = client.post(
            "/api/threads/t-a/runs/r-a/evidence-validation/replay",
            json={"quality_profile_id": "evidence-research-v1", "brief": valid_brief()},
        )
    assert response.status_code == 403
    assert service.process_run.await_count == 0


def test_manual_replay_rejects_non_allowed_profile_with_409():
    config = EvidenceValidationConfig(
        enabled=True,
        quality_profile_ids=["evidence-research-v1"],
        allowed_user_ids=[USER_A],
    )
    client, _, _, service = _make_client(run=_run(), config=config)
    with client:
        response = client.post(
            "/api/threads/t-a/runs/r-a/evidence-validation/replay",
            json={"quality_profile_id": "another-profile", "brief": valid_brief()},
        )
    assert response.status_code == 409
    assert service.process_run.await_count == 0


def test_owner_can_approve_review_required_report():
    stored = validation_record()
    approved = deepcopy(stored)
    approved["final_status"] = "confirmed"
    approved["review_decisions"] = [{"decision": "approved"}]
    client, _, repo, _ = _make_client(run=_run(), stored=stored)
    repo.submit_review.return_value = approved

    with client:
        response = client.post(
            "/api/threads/t-a/runs/r-a/evidence-validation/reviews",
            json={
                "decision": "approved",
                "expected_report_hash": stored["report_hash"],
                "idempotency_key": "approve-once",
            },
        )

    assert response.status_code == 200
    assert response.json()["final_status"] == "confirmed"
    repo.submit_review.assert_awaited_once_with(
        validation_id="v1",
        user_id=USER_A,
        decision="approved",
        expected_report_hash="hash-a",
        idempotency_key="approve-once",
        reason=None,
    )


def test_review_rejects_stale_report_hash_with_409():
    stored = validation_record()
    client, _, repo, _ = _make_client(run=_run(), stored=stored)
    repo.submit_review.side_effect = ValueError("报告版本已变化，请重新加载校验结果")

    with client:
        response = client.post(
            "/api/threads/t-a/runs/r-a/evidence-validation/reviews",
            json={
                "decision": "approved",
                "expected_report_hash": "stale",
                "idempotency_key": "approve-stale",
            },
        )

    assert response.status_code == 409
    assert "版本" in response.json()["detail"]
