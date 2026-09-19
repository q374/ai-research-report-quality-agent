"""结构化证据提交契约测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from deerflow.evaluation.evidence_submission import (
    EvidenceCandidate,
    EvidenceReportSubmission,
    extract_citation_urls,
    sanitize_citation_links,
    sanitize_source_url,
)


def make_claim(claim_id: str) -> dict:
    return {
        "claim_id": claim_id,
        "text": f"结论 {claim_id}",
        "claim_type": "current_fact",
        "dimension": "capability",
        "is_key": claim_id == "C0",
        "evidence_ids": ["E1"],
        "citation_evidence_ids": ["E1"],
    }


def make_evidence(evidence_id: str, *, excerpt: str = "证据摘要") -> dict:
    return {
        "evidence_id": evidence_id,
        "source_url": "https://example.com/doc?id=7",
        "title": "来源标题",
        "published_at": None,
        "excerpt": excerpt,
        "proposed_relation": "supports",
    }


def make_submission(*, claims: list[dict] | None = None, evidence: list[dict] | None = None) -> dict:
    return {
        "rendered_text": "结论。[citation:来源1](https://example.com/doc?id=7)",
        "claims": claims if claims is not None else [make_claim("C1")],
        "evidence": evidence if evidence is not None else [make_evidence("E1")],
    }


def test_submission_accepts_more_than_eight_claims_and_long_excerpt() -> None:
    payload = make_submission(
        claims=[make_claim(f"C{i}") for i in range(12)],
        evidence=[make_evidence("E1", excerpt="证" * 500)],
    )

    submission = EvidenceReportSubmission.model_validate(payload)

    assert len(submission.claims) == 12
    assert len(submission.evidence[0].excerpt) == 500


def test_evidence_candidate_rejects_agent_confirmed_status() -> None:
    with pytest.raises(ValidationError):
        EvidenceCandidate.model_validate({**make_evidence("E1"), "status": "confirmed"})


def test_urls_strip_userinfo_and_sensitive_query_values() -> None:
    safe = sanitize_source_url(
        "https://u:p@example.com/doc?token=secret&utm_source=x&id=7#part"
    )
    rendered = sanitize_citation_links(
        "结论。[citation:来源1](https://example.com/doc?api_key=secret&id=7)"
    )

    assert safe == "https://example.com/doc?id=7#part"
    assert rendered == "结论。[citation:来源1](https://example.com/doc?id=7)"
    assert "secret" not in rendered


def test_source_url_only_accepts_http_and_https() -> None:
    for value in ("file:///etc/passwd", "javascript:alert(1)", "ftp://example.com/a"):
        with pytest.raises(ValueError):
            sanitize_source_url(value)


def test_submission_sanitizes_structured_and_rendered_urls_consistently() -> None:
    payload = make_submission()
    payload["evidence"][0]["source_url"] = (
        "HTTPS://u:p@Example.COM/doc?access_token=secret&id=7#part"
    )
    payload["rendered_text"] = (
        "结论。[citation:来源1](HTTPS://u:p@Example.COM/doc?access_token=secret&id=7#part)"
    )

    submission = EvidenceReportSubmission.model_validate(payload)

    expected = "https://example.com/doc?id=7#part"
    assert submission.evidence[0].source_url == expected
    assert extract_citation_urls(submission.rendered_text) == [expected]


def test_event_payload_adds_only_system_owned_envelope_fields() -> None:
    submission = EvidenceReportSubmission.model_validate(make_submission())

    payload = submission.to_event_payload(message_id="message-1")

    assert payload["schema_version"] == "2.0"
    assert payload["message_id"] == "message-1"
    assert payload["rendered_text"] == submission.rendered_text
    assert payload["claims"][0]["claim_id"] == "C1"
    assert payload["evidence"][0]["evidence_id"] == "E1"
