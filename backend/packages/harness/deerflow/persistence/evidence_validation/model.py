"""ORM model for deterministic evidence-validation records."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from deerflow.persistence.base import Base


class EvidenceValidationRow(Base):
    __tablename__ = "evidence_validations"

    validation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quality_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    auto_status: Mapped[str] = mapped_column(String(32), nullable=False)
    final_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_decisions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    semantic_evaluation: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "report_hash",
            name="uq_evidence_validations_run_hash",
        ),
        Index(
            "ix_evidence_validations_user_thread_run",
            "user_id",
            "thread_id",
            "run_id",
        ),
    )
