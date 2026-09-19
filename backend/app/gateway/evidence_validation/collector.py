"""把持久化 run/event 转成确定性证据校验输入。"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SEARCH_TOOLS = {
    "search",
    "web_search",
    "tavily_search",
    "duckduckgo_search",
}
PAGE_TOOLS = {
    "crawl",
    "fetch_url",
    "read_url",
    "visit_page",
    "web_fetch",
}
AI_EVENT_TYPES = {"ai_message", "llm.ai.response"}
SENSITIVE_QUERY_KEYS = {
    "access_key",
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
}
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        for key in ("text", "content"):
            value = content.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, (list, Mapping)):
                nested = _message_text(value)
                if nested:
                    return nested
        return ""
    if isinstance(content, list):
        return "".join(_message_text(item) for item in content)
    return ""


def _walk_urls(value: object) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str):
        urls.extend(_URL_RE.findall(value))
    elif isinstance(value, Mapping):
        for nested in value.values():
            urls.extend(_walk_urls(nested))
    elif isinstance(value, list):
        for nested in value:
            urls.extend(_walk_urls(nested))
    return urls


def _sanitize_url(value: str) -> str:
    """只保留可审计 URL，并删除常见凭据查询参数与 userinfo。"""
    try:
        parts = urlsplit(value.rstrip(".,);]"))
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    host = parts.hostname.lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in SENSITIVE_QUERY_KEYS
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            host,
            parts.path or "/",
            urlencode(query),
            parts.fragment,
        )
    )


def _structured_list(primary: Mapping[str, Any], fallback: Mapping[str, Any], key: str) -> list[dict]:
    value = primary.get(key)
    if not isinstance(value, list):
        value = fallback.get(key)
    if not isinstance(value, list):
        return []
    return copy.deepcopy([item for item in value if isinstance(item, dict)])


def collect_shadow_payload(
    run: dict,
    events: list[dict],
    *,
    brief: dict,
    quality_profile_id: str,
    source: str,
) -> tuple[dict, str, str]:
    """采集系统事实；不从自然语言猜测 Claim/Evidence。"""
    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    data_gaps: list[str] = []
    rendered_text = run.get("last_ai_message")
    rendered_text = rendered_text if isinstance(rendered_text, str) else ""
    rendered_text = rendered_text.strip()
    if not rendered_text:
        data_gaps.append("empty_final_answer")

    ordered_events = sorted(
        [event for event in events if isinstance(event, dict)],
        key=lambda event: event.get("seq", 0),
    )
    if len(ordered_events) >= 500:
        data_gaps.append("event_limit_reached")

    observed_searches = 0
    observed_page_urls: list[str] = []
    used_tools: list[str] = []
    last_ai_text = ""
    message_id = ""
    latency_ms = 0

    for event in ordered_events:
        event_metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event_metadata.get("content_truncated") is True and "truncated_event_content" not in data_gaps:
            data_gaps.append("truncated_event_content")

        event_type = event.get("event_type")
        if event_type in AI_EVENT_TYPES:
            caller = event_metadata.get("caller")
            if caller not in (None, "lead_agent"):
                continue
            content = event.get("content")
            text = _message_text(content).strip()
            if text:
                last_ai_text = text
            if isinstance(content, Mapping) and content.get("id"):
                message_id = str(content["id"])
            elif event_metadata.get("message_id"):
                message_id = str(event_metadata["message_id"])
            value = event_metadata.get("latency_ms")
            if isinstance(value, (int, float)) and value >= 0:
                latency_ms += int(value)
            continue

        if event_type != "llm.tool.result":
            continue
        content = event.get("content")
        if not isinstance(content, Mapping):
            continue
        name = content.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        normalized_name = name.strip().lower()
        used_tools.append(normalized_name)
        if normalized_name in SEARCH_TOOLS:
            observed_searches += 1
        if normalized_name in PAGE_TOOLS:
            for field in ("content", "artifact"):
                for url in _walk_urls(content.get(field)):
                    safe_url = _sanitize_url(url)
                    if safe_url:
                        observed_page_urls.append(safe_url)

    if rendered_text and not last_ai_text:
        data_gaps.append("missing_final_answer_event")
    elif rendered_text and last_ai_text and rendered_text != last_ai_text:
        data_gaps.append("final_answer_event_mismatch")

    claims = _structured_list(brief, metadata, "claims")
    evidence = _structured_list(brief, metadata, "evidence")
    semantic_state = "evaluated" if claims and evidence else "not_evaluable"
    if semantic_state == "not_evaluable":
        data_gaps.append("missing_structured_claims_or_evidence")

    total_tokens = run.get("total_tokens")
    input_tokens = run.get("total_input_tokens")
    output_tokens = run.get("total_output_tokens")
    token_usage = {
        "input_tokens": input_tokens if isinstance(input_tokens, int) else 0,
        "output_tokens": output_tokens if isinstance(output_tokens, int) else 0,
        "total_tokens": total_tokens if isinstance(total_tokens, int) else 0,
        "llm_call_count": run.get("llm_call_count") if isinstance(run.get("llm_call_count"), int) else 0,
    }
    accessed_at = run.get("updated_at") or run.get("created_at") or "unknown"
    model_name = run.get("model_name") if isinstance(run.get("model_name"), str) else "unknown"

    payload = {
        "brief": copy.deepcopy(brief),
        "claims": claims,
        "evidence": evidence,
        "report": {
            "report_id": str(run.get("run_id") or "unknown-run"),
            "rendered_text": rendered_text,
            "observed_searches": observed_searches,
            "observed_page_urls": observed_page_urls,
            "used_tools": used_tools,
            "token_usage": token_usage,
            "latency_seconds": round(latency_ms / 1000, 3),
        },
        "audit": {
            "model": model_name,
            "prompt_version": quality_profile_id,
            "accessed_at": str(accessed_at),
            "cost_estimate_cny": run.get("cost_estimate_cny", 0),
            "human_review": "pending",
            "source": source,
            "quality_profile_id": quality_profile_id,
            "data_gaps": data_gaps,
        },
    }
    return payload, semantic_state, message_id or f"{run.get('run_id', 'unknown-run')}:final"
