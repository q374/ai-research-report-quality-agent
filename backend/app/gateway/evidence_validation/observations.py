"""从持久事件中恢复可审计的工具观察与证据提交。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from deerflow.evaluation.evidence_submission import (
    EvidenceReportSubmission,
    extract_citation_urls,
    sanitize_source_url,
)
from deerflow.evaluation.evidence_validator import canonicalize_url

SEARCH_TOOLS = {"search", "web_search", "tavily_search", "duckduckgo_search"}
PAGE_TOOLS = {"crawl", "fetch_url", "read_url", "visit_page", "web_fetch"}
AI_EVENT_TYPES = {"ai_message", "llm.ai.response"}


@dataclass(frozen=True)
class PageObservation:
    """一次由真实工具调用和工具结果配对得到的页面观察。"""

    tool_call_id: str
    tool_name: str
    source_url: str
    canonical_url: str
    content: str
    accessed_at: str
    truncated: bool


@dataclass(frozen=True)
class ObservationIndex:
    """一次运行中由系统事件确认的工具观察。"""

    observed_searches: int
    pages: list[PageObservation]
    used_tools: list[str]


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


def _ordered_events(events: list[dict]) -> list[dict]:
    return sorted(
        [event for event in events if isinstance(event, dict)],
        key=lambda event: event.get("seq", 0),
    )


def _tool_calls(content: object) -> list[Mapping[str, Any]]:
    if not isinstance(content, Mapping):
        return []
    value = content.get("tool_calls")
    if not isinstance(value, list):
        additional = content.get("additional_kwargs")
        if isinstance(additional, Mapping):
            value = additional.get("tool_calls")
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _call_url(call: Mapping[str, Any]) -> str:
    args = call.get("args")
    if not isinstance(args, Mapping):
        args = call.get("arguments")
    if not isinstance(args, Mapping):
        return ""
    for key in ("url", "source_url", "uri"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def collect_observations(events: list[dict]) -> ObservationIndex:
    """只用真实工具调用和对应结果构造观察索引。"""
    calls: dict[str, Mapping[str, Any]] = {}
    for event in _ordered_events(events):
        if event.get("event_type") not in AI_EVENT_TYPES:
            continue
        for call in _tool_calls(event.get("content")):
            call_id = call.get("id")
            if isinstance(call_id, str) and call_id:
                calls[call_id] = call

    searches = 0
    pages: list[PageObservation] = []
    used_tools: list[str] = []
    for event in _ordered_events(events):
        if event.get("event_type") != "llm.tool.result":
            continue
        content = event.get("content")
        if not isinstance(content, Mapping):
            continue
        name = content.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        tool_name = name.strip().lower()
        used_tools.append(tool_name)
        if tool_name in SEARCH_TOOLS:
            searches += 1
        if tool_name not in PAGE_TOOLS:
            continue

        call_id = content.get("tool_call_id")
        if not isinstance(call_id, str) or call_id not in calls:
            continue
        raw_url = _call_url(calls[call_id])
        try:
            safe_url = sanitize_source_url(raw_url)
        except ValueError:
            continue
        metadata = event.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        accessed_at = event.get("created_at") or metadata.get("accessed_at") or "unknown"
        pages.append(
            PageObservation(
                tool_call_id=call_id,
                tool_name=tool_name,
                source_url=safe_url,
                canonical_url=canonicalize_url(safe_url),
                content=_message_text(content.get("content")),
                accessed_at=str(accessed_at),
                truncated=metadata.get("content_truncated") is True,
            )
        )
    return ObservationIndex(searches, pages, used_tools)


def _final_ai_message_id(events: list[dict]) -> str:
    message_id = ""
    for event in _ordered_events(events):
        if event.get("event_type") not in AI_EVENT_TYPES:
            continue
        metadata = event.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        if metadata.get("caller") not in (None, "lead_agent"):
            continue
        content = event.get("content")
        if isinstance(content, Mapping) and content.get("id"):
            message_id = str(content["id"])
        elif metadata.get("message_id"):
            message_id = str(metadata["message_id"])
    return message_id


def select_evidence_submission(events: list[dict]) -> tuple[dict | None, list[str]]:
    """选择与最终 AI 消息匹配的最后一份合法证据提交。"""
    gaps: list[str] = []
    submission_events = [event for event in _ordered_events(events) if event.get("event_type") == "evidence.report.submitted"]
    if len(submission_events) > 1:
        gaps.append("duplicate_evidence_report_events")

    valid: list[dict] = []
    for event in submission_events:
        content = event.get("content")
        if not isinstance(content, Mapping):
            if "malformed_evidence_report" not in gaps:
                gaps.append("malformed_evidence_report")
            continue
        message_id = content.get("message_id")
        if content.get("schema_version") != "2.0" or not isinstance(message_id, str) or not message_id:
            if "malformed_evidence_report" not in gaps:
                gaps.append("malformed_evidence_report")
            continue
        try:
            submission = EvidenceReportSubmission.model_validate(
                {
                    "rendered_text": content.get("rendered_text"),
                    "claims": content.get("claims"),
                    "evidence": content.get("evidence"),
                }
            )
        except (ValidationError, ValueError):
            if "malformed_evidence_report" not in gaps:
                gaps.append("malformed_evidence_report")
            continue
        valid.append(submission.to_event_payload(message_id))

    final_message_id = _final_ai_message_id(events)
    for submission in reversed(valid):
        if submission["message_id"] == final_message_id:
            return submission, gaps
    if submission_events:
        gaps.append("evidence_report_message_mismatch")
    return None, gaps


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def apply_collection_status(submission: Mapping[str, Any], index: ObservationIndex) -> dict:
    """用系统观察补齐状态；忽略智能体自报的系统字段。"""
    claims = [dict(item) for item in submission.get("claims", []) if isinstance(item, Mapping)]
    evidence_items = [dict(item) for item in submission.get("evidence", []) if isinstance(item, Mapping)]
    findings: list[dict] = []
    evidence_by_id: dict[str, dict] = {}

    pages_by_url: dict[str, PageObservation] = {}
    for page in index.pages:
        pages_by_url[page.canonical_url] = page

    for item in evidence_items:
        try:
            safe_url = sanitize_source_url(str(item.get("source_url", "")))
        except ValueError:
            safe_url = ""
        item["source_url"] = safe_url
        canonical = canonicalize_url(safe_url)
        page = pages_by_url.get(canonical)
        item["canonical_url"] = canonical
        item["accessed_at"] = page.accessed_at if page else None
        item["collection_status"] = "truncated" if page and page.truncated else "observed" if page else "unobserved"
        item["review_status"] = "pending"
        evidence_id = str(item.get("evidence_id", ""))
        if evidence_id:
            evidence_by_id[evidence_id] = item
        if page and not page.truncated:
            excerpt = _normalized_text(item.get("excerpt"))
            page_text = _normalized_text(page.content)
            if excerpt and excerpt not in page_text:
                findings.append(
                    {
                        "rule_id": "excerpt_not_found",
                        "evidence_id": evidence_id,
                        "message": "证据摘录未在完整页面结果中找到。",
                    }
                )

    cited_ids = {str(evidence_id) for claim in claims for evidence_id in claim.get("citation_evidence_ids", []) if isinstance(claim.get("citation_evidence_ids"), list)}
    cited_urls = {canonicalize_url(url) for url in extract_citation_urls(str(submission.get("rendered_text", "")))}
    bound_urls = {item["canonical_url"] for evidence_id, item in evidence_by_id.items() if evidence_id in cited_ids and item.get("canonical_url")}
    if cited_urls != bound_urls:
        findings.append(
            {
                "rule_id": "citation_evidence_mismatch",
                "evidence_ids": sorted(cited_ids),
                "message": "可见引用链接与结论绑定的证据不一致。",
            }
        )

    unique_sources = {item["canonical_url"] for item in evidence_items if item.get("canonical_url")}
    metrics = {
        "rendered_char_count": len(str(submission.get("rendered_text", ""))),
        "claim_count": len(claims),
        "evidence_count": len(evidence_items),
        "citation_count": len(extract_citation_urls(str(submission.get("rendered_text", "")))),
        "excerpt_char_lengths": [len(str(item.get("excerpt", ""))) for item in evidence_items],
        "unique_source_count": len(unique_sources),
    }
    return {
        "claims": claims,
        "evidence": evidence_items,
        "metrics": metrics,
        "findings_input": findings,
    }
