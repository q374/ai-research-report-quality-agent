"""兼容入口：转发到 backend 内的唯一证据复核契约实现。"""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_SRC = Path(__file__).resolve().parents[1] / "backend" / "packages" / "harness"
if str(HARNESS_SRC) not in sys.path:
    sys.path.insert(0, str(HARNESS_SRC))

from deerflow.evaluation.evidence_review_workflow import (  # noqa: E402
    ALLOWED_DECISIONS,
    SCHEMA_VERSION,
    build_validation_record,
    refresh_validation_record,
    submit_review,
)

__all__ = [
    "ALLOWED_DECISIONS",
    "SCHEMA_VERSION",
    "build_validation_record",
    "refresh_validation_record",
    "submit_review",
]