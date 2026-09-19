"""影子证据校验服务测试。"""

from __future__ import annotations

import copy
import json
from unittest.mock import AsyncMock, Mock

import pytest

from app.gateway.evidence_validation.service import ShadowValidationService
from deerflow.config.evidence_validation_config import EvidenceValidationConfig


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


def successful_run(*, metadata: dict | None = None) -> dict:
    return {
        "run_id": "r1",
        "thread_id": "t1",
        "user_id": "u1",
        "status": "success",
        "last_ai_message": "真实最终回答",
        "total_tokens": 120,
        "llm_call_count": 2,
        "model_name": "deepseek-chat",
        "metadata": metadata or {},
    }


def make_service(
    run: dict | None,
    *,
    allowed_users: list[str] | None = None,
    record_builder=None,
) -> ShadowValidationService:
    run_store = Mock()
    run_store.get = AsyncMock(return_value=run)
    run_store.update_status = AsyncMock()
    event_store = Mock()
    event_store.list_events = AsyncMock(
        return_value=[
            {
                "seq": 1,
                "event_type": "llm.ai.response",
                "content": {"id": "msg-1", "content": "真实最终回答"},
                "metadata": {"caller": "lead_agent"},
            }
        ]
    )
    repository = Mock()
    stored: dict[tuple[str, str], dict] = {}

    async def upsert(record: dict) -> dict:
        key = (record["run_id"], record["report_hash"])
        stored.setdefault(key, copy.deepcopy(record))
        return copy.deepcopy(stored[key])

    repository.upsert = AsyncMock(side_effect=upsert)
    config = EvidenceValidationConfig(
        enabled=True,
        quality_profile_ids=["evidence-research-v1"],
        allowed_user_ids=allowed_users if allowed_users is not None else ["u1"],
    )
    kwargs = {}
    if record_builder is not None:
        kwargs["record_builder"] = record_builder
    return ShadowValidationService(
        run_store,
        event_store,
        repository,
        config_provider=lambda: config,
        **kwargs,
    )


@pytest.mark.anyio
async def test_ineligible_run_is_skipped():
    service = make_service(successful_run(), allowed_users=["u1"])

    result = await service.process_run(
        thread_id="t1", run_id="r1", owner_user_id="u2", source="auto"
    )

    assert result is None
    assert service.repository.upsert.await_count == 0


@pytest.mark.anyio
async def test_unsuccessful_run_is_skipped():
    run = successful_run()
    run["status"] = "error"
    service = make_service(run)

    result = await service.process_run(
        thread_id="t1", run_id="r1", owner_user_id="u1", source="auto"
    )

    assert result is None
    assert service.event_store.list_events.await_count == 0
    assert service.repository.upsert.await_count == 0


@pytest.mark.anyio
async def test_thread_run_mismatch_is_rejected():
    service = make_service(successful_run())

    with pytest.raises(LookupError):
        await service.process_run(
            thread_id="another-thread",
            run_id="r1",
            owner_user_id="u1",
            quality_profile_id="evidence-research-v1",
            brief=valid_brief(),
            source="manual_replay",
        )

    assert service.repository.upsert.await_count == 0


@pytest.mark.anyio
async def test_auto_mode_uses_only_run_metadata_profile_and_brief():
    metadata = {
        "quality_profile_id": "evidence-research-v1",
        "research_brief": valid_brief(),
    }
    service = make_service(successful_run(metadata=metadata))

    result = await service.process_run(
        thread_id="t1",
        run_id="r1",
        owner_user_id="u1",
        quality_profile_id="ignored-explicit-profile",
        brief={"task_id": "ignored"},
        source="auto",
    )

    assert result is not None
    assert result["quality_profile_id"] == "evidence-research-v1"
    assert result["source_payload"]["brief"] == valid_brief()
    assert result["source_payload"]["audit"]["source"] == "auto"


@pytest.mark.anyio
async def test_auto_mode_without_metadata_profile_is_skipped():
    service = make_service(successful_run(metadata={}))

    result = await service.process_run(
        thread_id="t1",
        run_id="r1",
        owner_user_id="u1",
        quality_profile_id="evidence-research-v1",
        brief=valid_brief(),
        source="auto",
    )

    assert result is None
    assert service.repository.upsert.await_count == 0


@pytest.mark.anyio
async def test_manual_replay_does_not_mutate_run_metadata():
    metadata = {"original": {"nested": [1, 2, 3]}}
    before = copy.deepcopy(metadata)
    service = make_service(successful_run(metadata=metadata))

    result = await service.process_run(
        thread_id="t1",
        run_id="r1",
        owner_user_id="u1",
        quality_profile_id="evidence-research-v1",
        brief=valid_brief(),
        source="manual_replay",
    )

    assert result is not None
    assert metadata == before
    assert result["source_payload"]["audit"]["source"] == "manual_replay"


@pytest.mark.anyio
async def test_validation_failure_does_not_change_run_status():
    failing_builder = Mock(side_effect=RuntimeError("internal secret"))
    service = make_service(successful_run(), record_builder=failing_builder)

    result = await service.process_run(
        thread_id="t1",
        run_id="r1",
        owner_user_id="u1",
        quality_profile_id="evidence-research-v1",
        brief=valid_brief(),
        source="manual_replay",
    )

    assert result is not None
    assert result["auto_status"] == "validator_error"
    assert "internal secret" not in json.dumps(result)
    assert service.run_store.update_status.await_count == 0


@pytest.mark.anyio
async def test_repeated_processing_returns_same_validation_id():
    service = make_service(successful_run())
    request = {
        "thread_id": "t1",
        "run_id": "r1",
        "owner_user_id": "u1",
        "quality_profile_id": "evidence-research-v1",
        "brief": valid_brief(),
        "source": "manual_replay",
    }

    first = await service.process_run(**request)
    second = await service.process_run(**request)

    assert first is not None and second is not None
    assert first["validation_id"] == second["validation_id"]
    assert service.repository.upsert.await_count == 2
