"""Create deterministic evidence-validation records.

Revision ID: 0003_evidence_validations
Revises: 0002_runs_token_usage
Create Date: 2026-09-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_evidence_validations"
down_revision: str | Sequence[str] | None = "0002_runs_token_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_validations",
        sa.Column("validation_id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("quality_profile_id", sa.String(length=64), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column("source_payload_json", sa.JSON(), nullable=False),
        sa.Column("validation_result_json", sa.JSON(), nullable=False),
        sa.Column("auto_status", sa.String(length=32), nullable=False),
        sa.Column("semantic_evaluation", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint(
            "run_id",
            "report_hash",
            name="uq_evidence_validations_run_hash",
        ),
    )
    op.create_index(
        "ix_evidence_validations_user_id",
        "evidence_validations",
        ["user_id"],
    )
    op.create_index(
        "ix_evidence_validations_thread_id",
        "evidence_validations",
        ["thread_id"],
    )
    op.create_index(
        "ix_evidence_validations_run_id",
        "evidence_validations",
        ["run_id"],
    )
    op.create_index(
        "ix_evidence_validations_user_thread_run",
        "evidence_validations",
        ["user_id", "thread_id", "run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evidence_validations_user_thread_run",
        table_name="evidence_validations",
    )
    op.drop_index("ix_evidence_validations_run_id", table_name="evidence_validations")
    op.drop_index(
        "ix_evidence_validations_thread_id",
        table_name="evidence_validations",
    )
    op.drop_index("ix_evidence_validations_user_id", table_name="evidence_validations")
    op.drop_table("evidence_validations")
