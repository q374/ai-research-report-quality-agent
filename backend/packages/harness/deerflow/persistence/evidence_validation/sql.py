"""SQLAlchemy repository for evidence-validation records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from deerflow.evaluation.evidence_review_workflow import submit_review as apply_review_decision
from deerflow.persistence.evidence_validation.model import EvidenceValidationRow
from deerflow.runtime.user_context import AUTO, _AutoSentinel, resolve_user_id
from deerflow.utils.time import coerce_iso


class EvidenceValidationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sf

    @staticmethod
    def _row_to_dict(row: EvidenceValidationRow) -> dict[str, Any]:
        data = row.to_dict()
        data["source_payload"] = data.pop("source_payload_json", {})
        data["validation_result"] = data.pop("validation_result_json", {})
        data["review_decisions"] = data.pop("review_decisions_json", None) or []
        data["final_status"] = data.get("final_status") or data.get("auto_status")
        data["owner_user_id"] = data.get("user_id")
        for key in ("created_at", "updated_at"):
            value = data.get(key)
            if isinstance(value, datetime):
                data[key] = coerce_iso(value)
        return data

    @staticmethod
    def _values(record: dict[str, Any]) -> dict[str, Any]:
        user_id = record.get("user_id") or record.get("owner_user_id")
        required = {
            "validation_id": record.get("validation_id"),
            "schema_version": record.get("schema_version"),
            "user_id": user_id,
            "thread_id": record.get("thread_id"),
            "run_id": record.get("run_id"),
            "message_id": record.get("message_id"),
            "quality_profile_id": record.get("quality_profile_id"),
            "report_hash": record.get("report_hash"),
            "auto_status": record.get("auto_status"),
            "semantic_evaluation": record.get("semantic_evaluation"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(
                "evidence validation record missing required fields: "
                + ", ".join(sorted(missing))
            )

        now = datetime.now(UTC)
        created_at = record.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        if not isinstance(created_at, datetime):
            created_at = now
        return {
            **required,
            "source_payload_json": record.get("source_payload", {}),
            "validation_result_json": record.get("validation_result", {}),
            "final_status": record.get("final_status") or record.get("auto_status"),
            "review_decisions_json": record.get("review_decisions", []),
            "created_at": created_at,
            "updated_at": now,
        }

    @staticmethod
    def _identity_stmt(run_id: str, report_hash: str):
        return select(EvidenceValidationRow).where(
            EvidenceValidationRow.run_id == run_id,
            EvidenceValidationRow.report_hash == report_hash,
        )

    async def upsert(self, record: dict[str, Any]) -> dict[str, Any]:
        """Insert once for ``(run_id, report_hash)`` and return the stored row."""
        values = self._values(record)
        identity = self._identity_stmt(values["run_id"], values["report_hash"])

        async with self._sf() as session:
            existing = (await session.execute(identity)).scalar_one_or_none()
            if existing is not None:
                return self._row_to_dict(existing)

            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "sqlite":
                statement = sqlite_insert(EvidenceValidationRow).values(**values)
                statement = statement.on_conflict_do_nothing(
                    index_elements=["run_id", "report_hash"]
                )
                await session.execute(statement)
            elif dialect == "postgresql":
                statement = postgresql_insert(EvidenceValidationRow).values(**values)
                statement = statement.on_conflict_do_nothing(
                    index_elements=["run_id", "report_hash"]
                )
                await session.execute(statement)
            else:
                session.add(EvidenceValidationRow(**values))
                try:
                    await session.flush()
                except IntegrityError:
                    await session.rollback()
            await session.commit()

            stored = (await session.execute(identity)).scalar_one()
            return self._row_to_dict(stored)

    async def get_by_run(
        self,
        thread_id: str,
        run_id: str,
        *,
        user_id: str | None | _AutoSentinel = AUTO,
    ) -> dict[str, Any] | None:
        resolved_user_id = resolve_user_id(
            user_id,
            method_name="EvidenceValidationRepository.get_by_run",
        )
        statement = select(EvidenceValidationRow).where(
            EvidenceValidationRow.thread_id == thread_id,
            EvidenceValidationRow.run_id == run_id,
        )
        if resolved_user_id is not None:
            statement = statement.where(
                EvidenceValidationRow.user_id == resolved_user_id
            )
        statement = statement.order_by(EvidenceValidationRow.created_at.desc()).limit(1)
        async with self._sf() as session:
            row = (await session.execute(statement)).scalar_one_or_none()
            return self._row_to_dict(row) if row is not None else None

    async def submit_review(
        self,
        *,
        validation_id: str,
        user_id: str,
        decision: str,
        expected_report_hash: str,
        idempotency_key: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Append one owner review bound to the exact report hash."""
        async with self._sf() as session:
            statement = (
                select(EvidenceValidationRow)
                .where(
                    EvidenceValidationRow.validation_id == validation_id,
                    EvidenceValidationRow.user_id == user_id,
                )
                .with_for_update()
            )
            row = (await session.execute(statement)).scalar_one_or_none()
            if row is None:
                raise LookupError("Evidence validation not found")

            current = self._row_to_dict(row)
            updated = apply_review_decision(
                current,
                actor_user_id=user_id,
                decision=decision,
                expected_report_hash=expected_report_hash,
                idempotency_key=idempotency_key,
                reason=reason,
            )
            row.final_status = str(updated["final_status"])
            row.review_decisions_json = updated["review_decisions"]
            await session.commit()
            await session.refresh(row)
            return self._row_to_dict(row)
