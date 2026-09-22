"""证据提交经过 SQLite 重启后的零费用闭环测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.gateway.evidence_validation.service import ShadowValidationService
from deerflow.config.evidence_validation_config import EvidenceValidationConfig
from deerflow.persistence.base import Base
from deerflow.persistence.evidence_validation.sql import EvidenceValidationRepository
from deerflow.runtime.events.store.db import DbRunEventStore
from deerflow.runtime.runs.store.memory import MemoryRunStore

pytestmark = pytest.mark.asyncio


def valid_brief() -> dict:
    return {
        "task_id": "T001-live",
        "required_dimensions": [],
        "allowed_domains": ["example.com"],
        "time_scope": "current",
        "max_searches": 5,
        "max_pages": 5,
        "max_chars": 1000,
        "forbidden_tools": [],
    }


def persisted_events(*, thread_id: str, run_id: str, user_id: str) -> list[dict]:
    rendered = "Alpha 是当前能力。[citation:来源1](https://example.com/doc)"
    common = {"thread_id": thread_id, "run_id": run_id, "user_id": user_id}
    return [
        {
            **common,
            "event_type": "human_message",
            "category": "message",
            "content": "研究 Alpha",
        },
        {
            **common,
            "event_type": "llm.ai.response",
            "category": "message",
            "content": {
                "id": "tool-message",
                "content": "",
                "tool_calls": [
                    {
                        "id": "search-1",
                        "name": "web_search",
                        "args": {"query": "Alpha"},
                    },
                    {
                        "id": "fetch-1",
                        "name": "web_fetch",
                        "args": {"url": "https://example.com/doc"},
                    },
                ],
            },
            "metadata": {"caller": "lead_agent"},
        },
        {
            **common,
            "event_type": "llm.tool.result",
            "category": "message",
            "content": {
                "name": "web_search",
                "tool_call_id": "search-1",
                "content": "搜索结果",
            },
        },
        {
            **common,
            "event_type": "llm.tool.result",
            "category": "message",
            "content": {
                "name": "web_fetch",
                "tool_call_id": "fetch-1",
                "content": "官方正文 Alpha",
            },
            "created_at": "2026-09-20T01:00:00+00:00",
        },
        {
            **common,
            "event_type": "evidence.report.submitted",
            "category": "trace",
            "content": {
                "schema_version": "2.0",
                "message_id": "report-live",
                "rendered_text": rendered,
                "claims": [
                    {
                        "claim_id": "C1",
                        "text": "Alpha 是当前能力",
                        "claim_type": "current_fact",
                        "dimension": "capability",
                        "is_key": True,
                        "evidence_ids": ["E1"],
                        "citation_evidence_ids": ["E1"],
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "E1",
                        "source_url": "https://example.com/doc",
                        "title": "来源",
                        "published_at": None,
                        "excerpt": "Alpha",
                        "proposed_relation": "supports",
                    }
                ],
            },
            "metadata": {"message_id": "report-live", "schema_version": "2.0"},
        },
        {
            **common,
            "event_type": "ai_message",
            "category": "message",
            "content": {"id": "report-live", "content": rendered},
            "metadata": {"caller": "lead_agent"},
        },
    ]


async def create_run(run_store: MemoryRunStore, *, run_id: str, with_events: bool) -> None:
    brief = valid_brief()
    await run_store.put(
        run_id,
        thread_id="thread-1",
        user_id="u1",
        status="running",
        model_name="offline-fake",
        metadata={
            "quality_profile_id": "evidence-research-v1",
            "research_brief": brief,
        },
    )
    await run_store.update_run_completion(
        run_id,
        status="success",
        total_tokens=42,
        llm_call_count=1,
        last_ai_message=("Alpha 是当前能力。[citation:来源1](https://example.com/doc)" if with_events else "没有结构化事件的回答"),
    )


async def test_persisted_events_survive_restart_and_validate_idempotently(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "persisted-flow.db"
    url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    first_engine = create_async_engine(url)
    async with first_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    first_store = DbRunEventStore(async_sessionmaker(first_engine, expire_on_commit=False))
    await first_store.put_batch(persisted_events(thread_id="thread-1", run_id="run-1", user_id="u1"))
    await first_engine.dispose()

    second_engine = create_async_engine(url)
    session_factory = async_sessionmaker(second_engine, expire_on_commit=False)
    event_store = DbRunEventStore(session_factory)
    repository = EvidenceValidationRepository(session_factory)
    run_store = MemoryRunStore()
    await create_run(run_store, run_id="run-1", with_events=True)
    run_before = dict(await run_store.get("run-1", user_id="u1") or {})
    config = EvidenceValidationConfig(
        enabled=True,
        quality_profile_ids=["evidence-research-v1"],
        allowed_user_ids=["u1"],
    )
    service = ShadowValidationService(
        run_store,
        event_store,
        repository,
        config_provider=lambda: config,
    )

    try:
        assert await event_store.list_events("thread-1", "run-1", user_id="u2") == []

        first = await service.process_run(
            thread_id="thread-1",
            run_id="run-1",
            owner_user_id="u1",
            source="auto",
        )
        second = await service.process_run(
            thread_id="thread-1",
            run_id="run-1",
            owner_user_id="u1",
            source="auto",
        )

        assert first is not None and second is not None
        assert first["semantic_evaluation"] == "evaluated", first["source_payload"]
        assert first["auto_status"] in {"blocked", "review_required"}
        assert first["run_id"] == "run-1"
        assert first["validation_id"] == second["validation_id"]
        assert first["report_hash"] == second["report_hash"]
        run_after = await run_store.get("run-1", user_id="u1")
        assert run_after is not None
        assert run_after["status"] == run_before["status"] == "success"
        assert run_after["llm_call_count"] == run_before["llm_call_count"] == 1
    finally:
        await second_engine.dispose()


async def test_missing_persisted_submission_is_not_evaluable(tmp_path: Path) -> None:
    db_path = tmp_path / "missing-events.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    run_store = MemoryRunStore()
    await create_run(run_store, run_id="run-missing", with_events=False)
    config = EvidenceValidationConfig(
        enabled=True,
        quality_profile_ids=["evidence-research-v1"],
        allowed_user_ids=["u1"],
    )
    service = ShadowValidationService(
        run_store,
        DbRunEventStore(session_factory),
        EvidenceValidationRepository(session_factory),
        config_provider=lambda: config,
    )

    try:
        record = await service.process_run(
            thread_id="thread-1",
            run_id="run-missing",
            owner_user_id="u1",
            source="auto",
        )

        assert record is not None
        assert record["semantic_evaluation"] == "not_evaluable"
    finally:
        await engine.dispose()
