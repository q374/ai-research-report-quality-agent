"""研究报告的结构化提交契约与引用链接脱敏。"""

from __future__ import annotations

import re
from typing import Literal, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_CITATION_LINK_RE = re.compile(
    r"\[citation:[^\]]+\]\((?P<url>[^\s)]+)\)",
    flags=re.IGNORECASE,
)
_TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api-key",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
}


def _drop_query_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized.startswith("utm_") or normalized in _TRACKING_QUERY_KEYS or normalized in _SENSITIVE_QUERY_KEYS


def sanitize_source_url(value: str) -> str:
    """仅保留安全的 HTTP(S) 来源 URL，并移除凭据与敏感查询参数。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source_url must be a non-empty HTTP(S) URL")

    parts = urlsplit(value.strip())
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("source_url must use HTTP or HTTPS")

    hostname = parts.hostname.lower()
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("source_url contains an invalid port") from exc
    netloc = f"{hostname}:{port}" if port is not None else hostname
    query = [(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True) if not _drop_query_key(key)]
    return urlunsplit((scheme, netloc, parts.path or "/", urlencode(query), parts.fragment))


def sanitize_citation_links(markdown: str) -> str:
    """对报告中 ``citation`` 链接应用与结构化来源相同的脱敏规则。"""
    if not isinstance(markdown, str):
        raise ValueError("rendered_text must be a string")

    def replace(match: re.Match[str]) -> str:
        safe_url = sanitize_source_url(match.group("url"))
        original = match.group(0)
        return original.replace(match.group("url"), safe_url, 1)

    return _CITATION_LINK_RE.sub(replace, markdown)


def extract_citation_urls(markdown: str) -> list[str]:
    """按报告出现顺序提取已经脱敏的 ``citation`` URL。"""
    sanitized = sanitize_citation_links(markdown)
    return [match.group("url") for match in _CITATION_LINK_RE.finditer(sanitized)]


class ClaimCandidate(BaseModel):
    """由研究智能体提出、等待系统校验的结论。"""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str
    claim_type: Literal["current_fact", "historical_fact", "review_question", "unknown"]
    dimension: str
    is_key: bool
    evidence_ids: list[str]
    citation_evidence_ids: list[str]


class EvidenceCandidate(BaseModel):
    """由研究智能体观察并提交、等待复核的证据候选。"""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_url: str
    title: str
    published_at: str | None = None
    excerpt: str
    proposed_relation: Literal["supports", "contradicts", "unclear"]

    @field_validator("source_url", mode="before")
    @classmethod
    def sanitize_url(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("source_url must be a string")
        return sanitize_source_url(value)


class EvidenceReportSubmission(BaseModel):
    """一次研究运行最终提交的用户报告与结构化证据。"""

    model_config = ConfigDict(extra="forbid")

    rendered_text: str
    claims: list[ClaimCandidate]
    evidence: list[EvidenceCandidate]

    @model_validator(mode="after")
    def sanitize_rendered_citations(self) -> Self:
        self.rendered_text = sanitize_citation_links(self.rendered_text)
        return self

    def to_event_payload(self, message_id: str) -> dict:
        """生成由系统补齐版本号与消息标识的持久事件载荷。"""
        return {
            "schema_version": "2.0",
            "message_id": message_id,
            "rendered_text": self.rendered_text,
            "claims": [claim.model_dump(mode="json") for claim in self.claims],
            "evidence": [item.model_dump(mode="json") for item in self.evidence],
        }
