#!/usr/bin/env python3
"""兼容入口：转发到 backend 内的唯一证据校验实现。"""

from __future__ import annotations

import sys
from pathlib import Path

HARNESS_SRC = Path(__file__).resolve().parents[1] / "backend" / "packages" / "harness"
if str(HARNESS_SRC) not in sys.path:
    sys.path.insert(0, str(HARNESS_SRC))

from deerflow.evaluation.evidence_validator import canonicalize_url, main, validate  # noqa: E402

__all__ = ["canonicalize_url", "main", "validate"]


if __name__ == "__main__":
    raise SystemExit(main())