"""持久事件的工具观察与证据提交选择测试。"""

from __future__ import annotations

from app.gateway.evidence_validation.observations import (
    apply_collection_status,
    collect_observations,
    select_evidence_submission,
)


def claim(*, citation_ids: list[str] | None = None) -> dict:
    return {
        "claim_id": "C1",
        "text": "Alpha 是当前能力",
        "claim_type": "current_fact",
        "dimension": "capability",
        "is_key": True,
        "evidence_ids": ["E1"],
        "citation_evidence_ids": citation_ids or ["E1"],
    }


def evidence(*, excerpt: str = "Alpha Beta", url: str | None = None) -> dict:
    return {
        "evidence_id": "E1",
        "source_url": url or "https://u:p@example.com/doc?token=secret&utm_source=x&id=7#part",
        "title": "来源",
        "published_at": None,
        "excerpt": excerpt,
        "proposed_relation": "supports",
    }


def submission_event(message_id: str = "report-1", *, seq: int = 4) -> dict:
    return {
        "seq": seq,
        "event_type": "evidence.report.submitted",
        "content": {
            "schema_version": "2.0",
            "message_id": message_id,
            "rendered_text": ("结论。[citation:来源1](https://example.com/doc?id=7#part)"),
            "claims": [claim()],
            "evidence": [evidence()],
        },
        "metadata": {"message_id": message_id, "schema_version": "2.0"},
    }


def final_ai_event(message_id: str = "report-1", *, seq: int = 5) -> dict:
    return {
        "seq": seq,
        "event_type": "ai_message",
        "content": {"id": message_id, "content": "最终报告"},
        "metadata": {"caller": "lead_agent"},
    }


def fetch_events(*, truncated: bool = False, body: str = "正文 Alpha   Beta 完整") -> list[dict]:
    return [
        {
            "seq": 1,
            "event_type": "llm.ai.response",
            "content": {
                "id": "tool-call-message",
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
                        "args": {"url": ("https://u:p@example.com/doc?token=secret&utm_source=x&id=7#part")},
                    },
                ],
            },
            "metadata": {"caller": "lead_agent"},
        },
        {
            "seq": 2,
            "event_type": "llm.tool.result",
            "content": {
                "name": "web_search",
                "tool_call_id": "search-1",
                "content": "search results",
            },
        },
        {
            "seq": 3,
            "event_type": "llm.tool.result",
            "content": {
                "name": "web_fetch",
                "tool_call_id": "fetch-1",
                "content": body,
            },
            "metadata": {"content_truncated": truncated},
            "created_at": "2026-09-20T01:00:00+00:00",
        },
    ]


def test_collect_observations_pairs_calls_and_results_using_safe_url() -> None:
    index = collect_observations(fetch_events())

    assert index.observed_searches == 1
    assert len(index.pages) == 1
    page = index.pages[0]
    assert page.tool_call_id == "fetch-1"
    assert page.source_url == "https://example.com/doc?id=7#part"
    assert "secret" not in page.source_url
    assert page.content.startswith("正文")
    assert page.accessed_at == "2026-09-20T01:00:00+00:00"


def test_apply_collection_status_marks_observed_and_computes_metrics() -> None:
    index = collect_observations(fetch_events())
    submission = submission_event()["content"]

    collected = apply_collection_status(submission, index)

    item = collected["evidence"][0]
    assert item["collection_status"] == "observed"
    assert item["review_status"] == "pending"
    assert item["canonical_url"] == "https://example.com/doc?id=7"
    assert item["accessed_at"] == "2026-09-20T01:00:00+00:00"
    assert collected["findings_input"] == []
    assert collected["metrics"]["claim_count"] == 1
    assert collected["metrics"]["evidence_count"] == 1
    assert collected["metrics"]["citation_count"] == 1
    assert collected["metrics"]["excerpt_char_lengths"] == [10]
    assert collected["metrics"]["unique_source_count"] == 1


def test_excerpt_not_found_in_complete_page_is_explicit_finding() -> None:
    index = collect_observations(fetch_events(body="完整正文但没有目标摘录"))

    collected = apply_collection_status(submission_event()["content"], index)

    assert collected["evidence"][0]["collection_status"] == "observed"
    assert collected["findings_input"][0]["rule_id"] == "excerpt_not_found"


def test_truncated_page_is_not_misclassified_as_missing_excerpt() -> None:
    index = collect_observations(fetch_events(truncated=True, body="部分正文"))

    collected = apply_collection_status(submission_event()["content"], index)

    assert collected["evidence"][0]["collection_status"] == "truncated"
    assert all(finding["rule_id"] != "excerpt_not_found" for finding in collected["findings_input"])


def test_unvisited_source_is_unobserved() -> None:
    index = collect_observations(fetch_events())
    payload = submission_event()["content"]
    payload["evidence"][0]["source_url"] = "https://example.com/not-visited"

    collected = apply_collection_status(payload, index)

    assert collected["evidence"][0]["collection_status"] == "unobserved"


def test_select_submission_prefers_last_event_matching_final_ai_message() -> None:
    events = [
        submission_event("old", seq=1),
        {"seq": 2, "event_type": "evidence.report.submitted", "content": "bad"},
        submission_event("report-1", seq=3),
        final_ai_event("report-1", seq=4),
    ]

    selected, gaps = select_evidence_submission(events)

    assert selected is not None
    assert selected["message_id"] == "report-1"
    assert "duplicate_evidence_report_events" in gaps
    assert "malformed_evidence_report" in gaps


def test_select_submission_rejects_message_version_mismatch() -> None:
    selected, gaps = select_evidence_submission([submission_event("report-1"), final_ai_event("different")])

    assert selected is None
    assert "evidence_report_message_mismatch" in gaps


def test_visible_citation_and_claim_binding_mismatch_is_explicit() -> None:
    index = collect_observations(fetch_events())
    payload = submission_event()["content"]
    payload["claims"][0]["citation_evidence_ids"] = []

    collected = apply_collection_status(payload, index)

    assert any(finding["rule_id"] == "citation_evidence_mismatch" for finding in collected["findings_input"])
