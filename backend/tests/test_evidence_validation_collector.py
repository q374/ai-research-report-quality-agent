"""影子证据校验采集器测试。"""

from __future__ import annotations

import json

from app.gateway.evidence_validation.collector import collect_shadow_payload
from deerflow.evaluation.evidence_validator import validate


def valid_brief(*, max_chars: int = 1000) -> dict:
    return {
        "task_id": "T001",
        "required_dimensions": [],
        "allowed_domains": ["example.com"],
        "time_scope": "current",
        "max_searches": 5,
        "max_pages": 5,
        "max_chars": max_chars,
        "forbidden_tools": [],
    }


def test_collector_uses_system_facts_not_model_self_report():
    payload, semantic_state, message_id = collect_shadow_payload(
        run={
            "run_id": "r1",
            "last_ai_message": "实际正文",
            "total_tokens": 120,
            "llm_call_count": 2,
            "model_name": "system-model",
        },
        events=[
            {
                "seq": 1,
                "event_type": "llm.ai.response",
                "category": "message",
                "content": {
                    "id": "msg-1",
                    "content": "实际正文",
                    "additional_kwargs": {"total_tokens": 999999},
                },
                "metadata": {"caller": "lead_agent", "latency_ms": 230},
            },
            {
                "seq": 2,
                "event_type": "llm.tool.result",
                "category": "message",
                "content": {
                    "name": "web_search",
                    "content": "https://example.com/a",
                    "additional_kwargs": {"reported_searches": 99},
                },
            },
        ],
        brief=valid_brief(max_chars=4),
        quality_profile_id="evidence-research-v1",
        source="manual_replay",
    )

    assert payload["report"]["rendered_text"] == "实际正文"
    assert payload["report"]["token_usage"]["total_tokens"] == 120
    assert payload["report"]["observed_searches"] == 1
    assert payload["audit"]["model"] == "system-model"
    assert payload["audit"]["source"] == "manual_replay"
    assert semantic_state == "not_evaluable"
    assert message_id == "msg-1"


def test_collector_preserves_page_views_but_validator_counts_unique_urls():
    payload, _, _ = collect_shadow_payload(
        run={"run_id": "r1", "last_ai_message": "正文"},
        events=[
            {
                "seq": 1,
                "event_type": "llm.tool.result",
                "content": {"name": "web_fetch", "content": "https://example.com/a#one"},
            },
            {
                "seq": 2,
                "event_type": "llm.tool.result",
                "content": {"name": "web_fetch", "content": "https://example.com/a#two"},
            },
        ],
        brief=valid_brief(),
        quality_profile_id="evidence-research-v1",
        source="auto",
    )

    assert payload["report"]["observed_page_urls"] == [
        "https://example.com/a#one",
        "https://example.com/a#two",
    ]
    result = validate(payload)
    assert result["metrics"]["page_views"] == 2
    assert result["metrics"]["unique_pages"] == 1


def test_collector_records_truncated_event_and_empty_answer_gaps():
    payload, semantic_state, _ = collect_shadow_payload(
        run={"run_id": "r1", "last_ai_message": ""},
        events=[
            {
                "seq": 1,
                "event_type": "llm.tool.result",
                "content": {"name": "web_fetch", "content": "https://example.com/a"},
                "metadata": {"content_truncated": True},
            }
        ],
        brief=valid_brief(max_chars=0),
        quality_profile_id="evidence-research-v1",
        source="auto",
    )

    assert payload["report"]["rendered_text"] == ""
    assert set(payload["audit"]["data_gaps"]) >= {
        "empty_final_answer",
        "truncated_event_content",
    }
    assert semantic_state == "not_evaluable"


def test_collector_records_final_answer_mismatch():
    payload, _, _ = collect_shadow_payload(
        run={"run_id": "r1", "last_ai_message": "系统保存的最终正文"},
        events=[
            {
                "seq": 1,
                "event_type": "llm.ai.response",
                "content": {"id": "msg-1", "content": "事件中的旧正文"},
                "metadata": {"caller": "lead_agent"},
            }
        ],
        brief=valid_brief(),
        quality_profile_id="evidence-research-v1",
        source="auto",
    )

    assert payload["report"]["rendered_text"] == "系统保存的最终正文"
    assert "final_answer_event_mismatch" in payload["audit"]["data_gaps"]


def test_collector_does_not_persist_full_sensitive_tool_arguments():
    payload, _, _ = collect_shadow_payload(
        run={"run_id": "r1", "last_ai_message": "正文"},
        events=[
            {
                "seq": 1,
                "event_type": "llm.tool.result",
                "content": {
                    "name": "web_fetch",
                    "content": {"url": "https://example.com/a?api_key=hidden&ok=1"},
                    "artifact": {
                        "request": {"api_key": "super-secret", "query": "private query"},
                        "source_url": "https://example.com/b?access_token=hidden&x=2",
                    },
                },
            }
        ],
        brief=valid_brief(),
        quality_profile_id="evidence-research-v1",
        source="manual_replay",
    )

    serialized = json.dumps(payload, ensure_ascii=False)
    assert "super-secret" not in serialized
    assert "private query" not in serialized
    assert "hidden" not in serialized
    assert payload["report"]["observed_page_urls"] == [
        "https://example.com/a?ok=1",
        "https://example.com/b?x=2",
    ]


def test_collector_uses_matching_persisted_submission_as_live_contract():
    rendered = "结论。[citation:来源1](https://example.com/doc?id=7)"
    payload, semantic_state, message_id = collect_shadow_payload(
        run={"run_id": "r-live", "last_ai_message": rendered},
        events=[
            {
                "seq": 1,
                "event_type": "llm.ai.response",
                "content": {
                    "id": "tool-call-message",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "fetch-1",
                            "name": "web_fetch",
                            "args": {"url": "https://example.com/doc?id=7"},
                        }
                    ],
                },
                "metadata": {"caller": "lead_agent"},
            },
            {
                "seq": 2,
                "event_type": "llm.tool.result",
                "content": {
                    "name": "web_fetch",
                    "tool_call_id": "fetch-1",
                    "content": "官方正文 Alpha Beta",
                },
                "created_at": "2026-09-20T01:00:00+00:00",
            },
            {
                "seq": 3,
                "event_type": "evidence.report.submitted",
                "content": {
                    "schema_version": "2.0",
                    "message_id": "report-live",
                    "rendered_text": rendered,
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
                            "source_url": "https://example.com/doc?id=7",
                            "title": "来源",
                            "published_at": None,
                            "excerpt": "Alpha Beta",
                            "proposed_relation": "supports",
                        }
                    ],
                },
                "metadata": {"message_id": "report-live", "schema_version": "2.0"},
            },
            {
                "seq": 4,
                "event_type": "ai_message",
                "content": {"id": "report-live", "content": rendered},
                "metadata": {"caller": "lead_agent"},
            },
        ],
        brief=valid_brief(),
        quality_profile_id="evidence-research-v1",
        source="auto",
        event_backend="db",
    )

    assert semantic_state == "evaluated"
    assert message_id == "report-live"
    assert payload["claims"][0]["claim_id"] == "C1"
    assert payload["evidence"][0]["collection_status"] == "observed"
    assert payload["evidence"][0]["review_status"] == "pending"
    assert payload["report"]["structure_metrics"]["rendered_char_count"] == len(rendered)
    assert payload["report"]["structure_metrics"]["claim_count"] == 1
    assert payload["audit"]["finding_inputs"] == []


def test_live_current_fact_with_historical_narrative_is_blocked():
    payload = {
        "brief": valid_brief(),
        "claims": [
            {
                "claim_id": "C-history-as-current",
                "text": "首批向 Pro 开放，Plus 和 Team 用户随后开放。",
                "claim_type": "current_fact",
                "dimension": "availability",
                "is_key": True,
                "evidence_ids": ["E-history"],
                "citation_evidence_ids": ["E-history"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "E-history",
                "source_url": "https://example.com/launch",
                "canonical_url": "https://example.com/launch",
                "title": "发布公告",
                "published_at": "2025-02-02",
                "accessed_at": "2026-09-20",
                "excerpt": "Initially available to Pro users, with Plus and Team to follow.",
                "collection_status": "observed",
                "review_status": "pending",
            }
        ],
        "report": {
            "report_id": "r-history-as-current",
            "rendered_text": "首批向 Pro 开放，Plus 和 Team 用户随后开放。",
            "observed_searches": 1,
            "observed_page_urls": ["https://example.com/launch"],
            "used_tools": ["web_search", "web_fetch"],
            "token_usage": {},
            "latency_seconds": 1,
        },
        "audit": {
            "model": "fake-model",
            "prompt_version": "evidence-research-v1",
            "accessed_at": "2026-09-20",
            "cost_estimate_cny": 0,
            "human_review": "pending",
        },
    }

    result = validate(payload)

    currentness_findings = [
        finding for finding in result["findings"] if finding["rule_id"] == "EV-01"
    ]
    assert result["status"] == "blocked"
    assert len(currentness_findings) == 1
    assert "historical_fact" in currentness_findings[0]["required_action"]


def test_malformed_live_submission_cannot_fall_back_to_self_reported_metadata():
    payload, semantic_state, _ = collect_shadow_payload(
        run={
            "run_id": "r-malformed",
            "last_ai_message": "正文",
            "metadata": {
                "claims": [{"claim_id": "invented"}],
                "evidence": [{"evidence_id": "invented"}],
            },
        },
        events=[
            {
                "seq": 1,
                "event_type": "evidence.report.submitted",
                "content": "不是合法结构",
            },
            {
                "seq": 2,
                "event_type": "ai_message",
                "content": {"id": "report-live", "content": "正文"},
                "metadata": {"caller": "lead_agent"},
            },
        ],
        brief=valid_brief(),
        quality_profile_id="evidence-research-v1",
        source="auto",
        event_backend="db",
    )

    assert semantic_state == "not_evaluable"
    assert payload["claims"] == []
    assert payload["evidence"] == []
    assert "malformed_evidence_report" in payload["audit"]["data_gaps"]
