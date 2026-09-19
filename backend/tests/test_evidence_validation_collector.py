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
