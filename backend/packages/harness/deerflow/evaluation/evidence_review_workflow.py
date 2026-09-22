"""证据校验记录与人工复核状态机的离线契约。"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from deerflow.evaluation.evidence_validator import validate

SCHEMA_VERSION = "1.0"
ALLOWED_DECISIONS = {"approved", "returned", "rejected"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _report_hash(payload: dict) -> str:
    versioned_content = {
        "brief": payload.get("brief"),
        "rendered_text": (payload.get("report") or {}).get("rendered_text"),
        "claims": payload.get("claims"),
        "evidence": payload.get("evidence"),
    }
    canonical = json.dumps(
        versioned_content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validator_error_result(payload: dict) -> dict:
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    rendered_text = report.get("rendered_text") if isinstance(report.get("rendered_text"), str) else ""
    observed_urls = report.get("observed_page_urls")
    observed_urls = observed_urls if isinstance(observed_urls, list) else []
    searches = report.get("observed_searches") if isinstance(report.get("observed_searches"), int) else 0
    task_id = None
    if isinstance(payload.get("brief"), dict):
        task_id = payload["brief"].get("task_id")
    return {
        "task_id": task_id,
        "status": "validator_error",
        "metrics": {
            "actual_chars": len(rendered_text),
            "page_views": len(observed_urls),
            "unique_pages": 0,
            "searches": searches,
        },
        "finding_counts": {"blocker": 1, "warning": 0, "info": 0},
        "findings": [
            {
                "rule_id": "EV-10",
                "severity": "blocker",
                "claim_id": None,
                "evidence_ids": [],
                "message": "校验器执行异常，系统已按 fail-closed 阻断。",
                "required_action": "检查校验服务后重新执行，不得绕过门禁。",
            }
        ],
    }


def build_validation_record(
    payload: dict,
    *,
    thread_id: str,
    run_id: str,
    message_id: str,
    owner_user_id: str,
    validator_func: Callable[[dict], dict] = validate,
    now: str | None = None,
) -> dict:
    """建立与具体报告版本绑定的校验记录。"""
    source_payload = copy.deepcopy(payload)
    report_hash = _report_hash(source_payload)
    try:
        validation_result = validator_func(source_payload)
        if not isinstance(validation_result, dict):
            raise TypeError("校验器必须返回字典")
    except Exception:
        validation_result = _validator_error_result(source_payload)

    auto_status = validation_result.get("status", "validator_error")
    if auto_status not in {"blocked", "review_required"}:
        auto_status = "validator_error"
        validation_result = _validator_error_result(source_payload)

    validation_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"evidence-validation:{thread_id}:{run_id}:{message_id}:{report_hash}",
        )
    )
    return {
        "validation_id": validation_id,
        "schema_version": SCHEMA_VERSION,
        "thread_id": thread_id,
        "run_id": run_id,
        "message_id": message_id,
        "owner_user_id": owner_user_id,
        "report_hash": report_hash,
        "source_payload": source_payload,
        "validation_result": validation_result,
        "auto_status": auto_status,
        "final_status": auto_status,
        "review_decisions": [],
        "created_at": now or _utc_now(),
    }


def submit_review(
    record: dict,
    *,
    actor_user_id: str,
    decision: str,
    expected_report_hash: str,
    idempotency_key: str,
    reason: str | None = None,
    now: str | None = None,
) -> dict:
    """校验权限、版本和状态后追加一次人工决定。"""
    if actor_user_id != record.get("owner_user_id"):
        raise PermissionError("当前用户无权复核该线程的报告")
    if expected_report_hash != record.get("report_hash"):
        raise ValueError("报告版本已变化，请重新加载校验结果")
    if decision not in ALLOWED_DECISIONS:
        raise ValueError("不支持的人工决定")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("idempotency_key 不能为空")

    normalized_reason = (reason or "").strip()
    if decision in {"returned", "rejected"} and not normalized_reason:
        raise ValueError("退回或驳回必须填写理由")

    existing_decisions = record.get("review_decisions")
    existing_decisions = existing_decisions if isinstance(existing_decisions, list) else []
    for existing in existing_decisions:
        if existing.get("idempotency_key") != idempotency_key:
            continue
        same_request = existing.get("reviewer_user_id") == actor_user_id and existing.get("decision") == decision and existing.get("reason", "") == normalized_reason and existing.get("report_hash") == expected_report_hash
        if not same_request:
            raise ValueError("同一幂等键不能用于不同的人工决定")
        return copy.deepcopy(record)

    if existing_decisions:
        raise ValueError("当前报告版本已有人工决定，请重新校验后再提交")

    if decision == "approved" and record.get("final_status") != "review_required":
        raise ValueError("只有无阻断且仍处于待复核状态的报告可以批准")

    decision_id = hashlib.sha256(f"{record.get('validation_id')}:{idempotency_key}".encode()).hexdigest()[:24]
    review = {
        "decision_id": decision_id,
        "validation_id": record.get("validation_id"),
        "decision": decision,
        "reviewer_user_id": actor_user_id,
        "reason": normalized_reason,
        "report_hash": expected_report_hash,
        "idempotency_key": idempotency_key,
        "created_at": now or _utc_now(),
    }

    updated = copy.deepcopy(record)
    updated.setdefault("review_decisions", []).append(review)
    if decision == "approved":
        updated["final_status"] = "confirmed"
    elif decision == "rejected":
        updated["final_status"] = "rejected"
    else:
        updated["final_status"] = "blocked"
    return updated


def refresh_validation_record(
    record: dict,
    payload: dict,
    *,
    validator_func: Callable[[dict], dict] = validate,
    now: str | None = None,
) -> dict:
    """报告内容变化后创建新版本，并使旧人工决定失效。"""
    return build_validation_record(
        payload,
        thread_id=str(record.get("thread_id", "")),
        run_id=str(record.get("run_id", "")),
        message_id=str(record.get("message_id", "")),
        owner_user_id=str(record.get("owner_user_id", "")),
        validator_func=validator_func,
        now=now,
    )
