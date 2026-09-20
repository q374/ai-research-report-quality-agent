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


def make_live_payload(
    *,
    collection_status: str = "observed",
    review_status: str = "pending",
    finding_inputs: list[dict] | None = None,
) -> dict:
    return {
        "brief": {
            "task_id": "live-contract",
            "required_dimensions": [],
            "allowed_domains": ["example.com"],
            "time_scope": "current",
            "max_searches": 2,
            "max_pages": 2,
            "max_chars": 500,
            "forbidden_tools": [],
        },
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
                "canonical_url": "https://example.com/doc",
                "title": "来源",
                "published_at": None,
                "accessed_at": "2026-09-20T01:00:00+00:00",
                "excerpt": "Alpha",
                "proposed_relation": "supports",
                "collection_status": collection_status,
                "review_status": review_status,
            }
        ],
        "report": {
            "report_id": "r-live",
            "rendered_text": "Alpha 是当前能力",
            "observed_searches": 1,
            "observed_page_urls": ["https://example.com/doc"],
            "used_tools": ["web_search", "web_fetch"],
            "token_usage": {"total_tokens": 0},
            "latency_seconds": 0,
        },
        "audit": {
            "model": "offline-test",
            "prompt_version": "evidence-research-v1",
            "accessed_at": "2026-09-20T01:00:00+00:00",
            "cost_estimate_cny": 0,
            "human_review": "pending",
            "finding_inputs": finding_inputs or [],
        },
    }


def test_observed_pending_source_reaches_human_review_not_confirmed():
    from deerflow.evaluation.evidence_validator import validate

    result = validate(make_live_payload())

    assert result["status"] == "review_required"
    assert result["finding_counts"]["blocker"] == 0


def test_unobserved_source_blocks_even_if_legacy_status_is_confirmed():
    from deerflow.evaluation.evidence_validator import validate

    payload = make_live_payload(collection_status="unobserved")
    payload["evidence"][0]["status"] = "confirmed"
    payload["evidence"][0]["current_source"] = True

    result = validate(payload)

    assert result["status"] == "blocked"
    assert any(item["rule_id"] == "EV-11" for item in result["findings"])


def test_truncated_source_requires_review_without_false_blocker():
    from deerflow.evaluation.evidence_validator import validate

    result = validate(make_live_payload(collection_status="truncated"))

    assert result["status"] == "review_required"
    assert result["finding_counts"]["blocker"] == 0


def test_system_collection_findings_block_release():
    from deerflow.evaluation.evidence_validator import validate

    payload = make_live_payload(
        finding_inputs=[
            {"rule_id": "excerpt_not_found", "evidence_id": "E1"},
            {
                "rule_id": "citation_evidence_mismatch",
                "evidence_ids": ["E1"],
            },
        ]
    )

    result = validate(payload)

    assert result["status"] == "blocked"
    assert {item["rule_id"] for item in result["findings"]} >= {"EV-12", "EV-05"}


def test_legacy_b0_clean_fixture_keeps_original_status():
    from deerflow.evaluation.evidence_validator import validate

    result = validate(load_fixture("b0_clean_current"))

    assert result["status"] == "review_required"
    assert result["finding_counts"]["blocker"] == 0
