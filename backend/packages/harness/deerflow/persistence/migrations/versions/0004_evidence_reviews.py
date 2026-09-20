"""Persist manual review state for evidence validations.

Revision ID: 0004_evidence_reviews
Revises: 0003_evidence_validations
Create Date: 2026-09-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_evidence_reviews"
down_revision: str | Sequence[str] | None = "0003_evidence_validations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_validations",
        sa.Column("final_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "evidence_validations",
        sa.Column("review_decisions_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_validations", "review_decisions_json")
    op.drop_column("evidence_validations", "final_status")
