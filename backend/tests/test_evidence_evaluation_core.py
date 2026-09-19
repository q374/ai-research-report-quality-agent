from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_fixture(name: str) -> dict:
    path = REPO_ROOT / "tests" / "product" / "fixtures" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_backend_core_matches_legacy_entrypoint():
    from scripts.evidence_validator import validate as legacy_validate

    from deerflow.evaluation.evidence_validator import validate as backend_validate

    payload = load_fixture("t001_v3")
    assert backend_validate(payload) == legacy_validate(payload)


def test_automatic_validator_cannot_confirm():
    from deerflow.evaluation.evidence_review_workflow import build_validation_record

    record = build_validation_record(
        load_fixture("b0_clean_current"),
        thread_id="t1",
        run_id="r1",
        message_id="m1",
        owner_user_id="u1",
        validator_func=lambda _: {"status": "confirmed", "findings": [], "metrics": {}},
        now="2026-09-19T10:00:00+08:00",
    )

    assert record["final_status"] == "validator_error"


def test_legacy_wrappers_reexport_backend_functions():
    from scripts.evidence_review_workflow import build_validation_record as legacy_build
    from scripts.evidence_validator import validate as legacy_validate

    from deerflow.evaluation.evidence_review_workflow import (
        build_validation_record as backend_build,
    )
    from deerflow.evaluation.evidence_validator import validate as backend_validate

    assert legacy_validate is backend_validate
    assert legacy_build is backend_build