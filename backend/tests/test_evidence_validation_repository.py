from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from deerflow.persistence.base import Base
from deerflow.persistence.evidence_validation.model import EvidenceValidationRow
from deerflow.persistence.evidence_validation.sql import EvidenceValidationRepository

pytestmark = pytest.mark.asyncio


def sample_record(*, user_id: str = "u1", report_hash: str = "a" * 64) -> dict:
    return {
        "validation_id": "validation-1",
        "schema_version": "1.0",
        "user_id": user_id,
        "thread_id": "t1",
        "run_id": "r1",
        "message_id": "m1",
        "quality_profile_id": "evidence-research-v1",
        "report_hash": report_hash,
        "source_payload": {"brief": {"task_id": "task-1"}},
        "validation_result": {"status": "review_required", "findings": []},
        "auto_status": "review_required",
        "semantic_evaluation": "not_evaluable",
        "created_at": "2026-09-19T10:00:00+00:00",
    }


async def make_repository(db_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, EvidenceValidationRepository(async_sessionmaker(engine, expire_on_commit=False))


async def count_rows(repo: EvidenceValidationRepository) -> int:
    async with repo.session_factory() as session:
        result = await session.execute(select(func.count()).select_from(EvidenceValidationRow))
        return int(result.scalar_one())


async def test_upsert_is_idempotent(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "idempotent.db")
    try:
        first = await repo.upsert(sample_record())
        second = await repo.upsert(sample_record())

        assert first["validation_id"] == second["validation_id"]
        assert await count_rows(repo) == 1
    finally:
        await engine.dispose()


async def test_concurrent_upsert_returns_one_record(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "concurrent.db")
    try:
        first, second = await asyncio.gather(
            repo.upsert(sample_record()),
            repo.upsert(sample_record()),
        )

        assert first["validation_id"] == second["validation_id"]
        assert await count_rows(repo) == 1
    finally:
        await engine.dispose()


async def test_get_by_run_enforces_owner(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "owner.db")
    try:
        await repo.upsert(sample_record(user_id="u1"))

        assert await repo.get_by_run("t1", "r1", user_id="u1") is not None
        assert await repo.get_by_run("t1", "r1", user_id="u2") is None
    finally:
        await engine.dispose()


async def test_record_survives_sqlite_restart(tmp_path: Path):
    db_path = tmp_path / "restart.db"
    engine, repo = await make_repository(db_path)
    stored = await repo.upsert(sample_record())
    await engine.dispose()

    reopened = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    try:
        reopened_repo = EvidenceValidationRepository(async_sessionmaker(reopened, expire_on_commit=False))
        loaded = await reopened_repo.get_by_run("t1", "r1", user_id="u1")

        assert loaded is not None
        assert loaded["validation_id"] == stored["validation_id"]
        assert loaded["report_hash"] == stored["report_hash"]
        assert loaded["source_payload"]["brief"]["task_id"] == "task-1"
    finally:
        await reopened.dispose()


async def test_review_decision_is_persisted_and_idempotent(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "review.db")
    try:
        stored = await repo.upsert(sample_record())

        first = await repo.submit_review(
            validation_id=stored["validation_id"],
            user_id="u1",
            decision="approved",
            expected_report_hash=stored["report_hash"],
            idempotency_key="approve-once",
        )
        second = await repo.submit_review(
            validation_id=stored["validation_id"],
            user_id="u1",
            decision="approved",
            expected_report_hash=stored["report_hash"],
            idempotency_key="approve-once",
        )

        assert first["final_status"] == second["final_status"] == "confirmed"
        assert len(first["review_decisions"]) == len(second["review_decisions"]) == 1
        assert first["review_decisions"][0]["reviewer_user_id"] == "u1"

        reopened = await repo.get_by_run("t1", "r1", user_id="u1")
        assert reopened is not None
        assert reopened["final_status"] == "confirmed"
        assert reopened["review_decisions"] == first["review_decisions"]
    finally:
        await engine.dispose()


async def test_review_rejects_stale_hash_and_blocked_approval(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "review-guard.db")
    try:
        stored = await repo.upsert(sample_record())
        with pytest.raises(ValueError, match="版本已变化"):
            await repo.submit_review(
                validation_id=stored["validation_id"],
                user_id="u1",
                decision="approved",
                expected_report_hash="stale",
                idempotency_key="stale",
            )

        blocked = sample_record(report_hash="b" * 64)
        blocked["validation_id"] = "validation-blocked"
        blocked["run_id"] = "r-blocked"
        blocked["auto_status"] = "blocked"
        blocked["validation_result"] = {"status": "blocked", "findings": []}
        await repo.upsert(blocked)
        with pytest.raises(ValueError, match="待复核"):
            await repo.submit_review(
                validation_id=blocked["validation_id"],
                user_id="u1",
                decision="approved",
                expected_report_hash=blocked["report_hash"],
                idempotency_key="blocked",
            )
    finally:
        await engine.dispose()


async def test_concurrent_different_reviews_accept_only_one_decision(tmp_path: Path):
    engine, repo = await make_repository(tmp_path / "review-concurrent.db")
    try:
        stored = await repo.upsert(sample_record())

        outcomes = await asyncio.gather(
            repo.submit_review(
                validation_id=stored["validation_id"],
                user_id="u1",
                decision="approved",
                expected_report_hash=stored["report_hash"],
                idempotency_key="approve-concurrent",
            ),
            repo.submit_review(
                validation_id=stored["validation_id"],
                user_id="u1",
                decision="rejected",
                expected_report_hash=stored["report_hash"],
                idempotency_key="reject-concurrent",
                reason="证据不充分",
            ),
            return_exceptions=True,
        )

        successes = [item for item in outcomes if isinstance(item, dict)]
        failures = [item for item in outcomes if isinstance(item, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], ValueError)

        loaded = await repo.get_by_run("t1", "r1", user_id="u1")
        assert loaded is not None
        assert len(loaded["review_decisions"]) == 1
    finally:
        await engine.dispose()
