#!/usr/bin/env python3
"""离线、确定性的研究证据校验器。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
NEGATIVE_MARKERS = ("没有", "未披露", "未列明", "未找到", "无法确认", "未知")
RISK_EVENT_TERMS = ("暂停", "取消", "涨价", "降价", "下线", "停止注册", "停止开放")
HISTORICAL_NARRATIVE_MARKERS = (
    "发布时",
    "上线时",
    "首发",
    "首批",
    "当时",
    "曾于",
)
CONTRADICTION_GROUPS = (
    {
        "claim_terms": ("幻觉", "错误推断", "权威", "置信度", "模型质量"),
        "evidence_terms": (
            "hallucinate",
            "incorrect inference",
            "authoritative",
            "confidence calibration",
        ),
    },
    {
        "claim_terms": ("量化", "准确率", "指标", "基准"),
        "evidence_terms": ("26.6", "accuracy", "benchmark"),
    },
)


def canonicalize_url(url: str) -> str:
    """移除锚点和常见跟踪参数，稳定化协议、域名与查询参数。"""
    if not isinstance(url, str) or not url.strip():
        return ""
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(sorted(query)),
            "",
        )
    )


def _finding(
    rule_id: str,
    severity: str,
    message: str,
    required_action: str,
    claim_id: str | None = None,
    evidence_ids: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "claim_id": claim_id,
        "evidence_ids": evidence_ids or [],
        "message": message,
        "required_action": required_action,
    }


def _missing_fields(item: object, fields: tuple[str, ...]) -> list[str]:
    if not isinstance(item, dict):
        return list(fields)
    return [field for field in fields if field not in item]


def _collection_status(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("collection_status")
    return value if isinstance(value, str) else None


def _review_status(item: object) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("review_status", item.get("status"))
    return value if isinstance(value, str) else None


def _is_live_evidence(item: object) -> bool:
    return isinstance(item, dict) and "collection_status" in item


def _missing_evidence_fields(item: object) -> list[str]:
    common = (
        "evidence_id",
        "source_url",
        "canonical_url",
        "title",
        "published_at",
        "accessed_at",
        "excerpt",
    )
    missing = _missing_fields(item, common)
    if not isinstance(item, dict):
        return missing
    if _is_live_evidence(item):
        missing.extend(_missing_fields(item, ("collection_status", "review_status")))
    else:
        missing.extend(_missing_fields(item, ("status",)))
    return missing


def validate(payload: dict) -> dict:
    """校验一份结构化研究结果并返回发布状态与问题清单。"""
    if not isinstance(payload, dict):
        payload = {}

    findings: list[dict] = []
    brief = payload.get("brief") if isinstance(payload.get("brief"), dict) else {}
    claims = payload.get("claims") if isinstance(payload.get("claims"), list) else []
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
    audit = payload.get("audit") if isinstance(payload.get("audit"), dict) else {}

    contract_requirements = {
        "brief": (
            "task_id",
            "required_dimensions",
            "allowed_domains",
            "time_scope",
            "max_searches",
            "max_pages",
            "max_chars",
            "forbidden_tools",
        ),
        "report": (
            "report_id",
            "rendered_text",
            "observed_searches",
            "observed_page_urls",
            "used_tools",
            "token_usage",
            "latency_seconds",
        ),
        "audit": (
            "model",
            "prompt_version",
            "accessed_at",
            "cost_estimate_cny",
            "human_review",
        ),
    }
    sections = {"brief": brief, "report": report, "audit": audit}
    missing_sections = [name for name in ("brief", "claims", "evidence", "report", "audit") if name not in payload]
    missing_details = {
        name: _missing_fields(sections[name], fields)
        for name, fields in contract_requirements.items()
        if _missing_fields(sections[name], fields)
    }
    if missing_sections or missing_details:
        details = []
        if missing_sections:
            details.append("缺少对象：" + "、".join(missing_sections))
        for name, fields in missing_details.items():
            details.append(f"{name} 缺少字段：{'、'.join(fields)}")
        findings.append(
            _finding(
                "EV-10",
                "blocker",
                "；".join(details),
                "补齐最小输入契约后重新校验；契约不完整时默认阻断。",
            )
        )

    evidence_by_id = {
        item.get("evidence_id"): item
        for item in evidence
        if isinstance(item, dict) and item.get("evidence_id")
    }

    claim_fields = ("claim_id", "text", "claim_type", "dimension", "evidence_ids")
    malformed_claims = [
        index for index, item in enumerate(claims) if _missing_fields(item, claim_fields)
    ]
    malformed_evidence = [
        index for index, item in enumerate(evidence) if _missing_evidence_fields(item)
    ]
    if malformed_claims or malformed_evidence:
        parts = []
        if malformed_claims:
            parts.append("Claim 索引 " + "、".join(map(str, malformed_claims)))
        if malformed_evidence:
            parts.append("EvidenceItem 索引 " + "、".join(map(str, malformed_evidence)))
        findings.append(
            _finding(
                "EV-10",
                "blocker",
                "最小字段不完整：" + "；".join(parts),
                "补齐对象最小字段后重新校验。",
            )
        )

    # EV-11：新 live contract 只相信系统计算的采集状态。
    for item in evidence:
        if not _is_live_evidence(item):
            continue
        evidence_id = str(item.get("evidence_id", ""))
        collection_status = _collection_status(item)
        if collection_status == "unobserved":
            findings.append(
                _finding(
                    "EV-11",
                    "blocker",
                    "证据来源未在本次运行的真实页面访问记录中出现。",
                    "实际访问该来源并重新提交，不能依赖模型自报。",
                    evidence_ids=[evidence_id] if evidence_id else [],
                )
            )
        elif collection_status == "truncated":
            findings.append(
                _finding(
                    "EV-11",
                    "warning",
                    "页面结果被截断，系统无法完整核对证据摘录。",
                    "由人工复核原页面，或重新获取完整正文。",
                    evidence_ids=[evidence_id] if evidence_id else [],
                )
            )
        elif collection_status != "observed":
            findings.append(
                _finding(
                    "EV-11",
                    "blocker",
                    "证据缺少有效的系统采集状态。",
                    "修复事件采集后重新校验。",
                    evidence_ids=[evidence_id] if evidence_id else [],
                )
            )

    finding_inputs = audit.get("finding_inputs")
    finding_inputs = finding_inputs if isinstance(finding_inputs, list) else []
    for item in finding_inputs:
        if not isinstance(item, dict):
            continue
        rule_id = item.get("rule_id")
        if rule_id == "excerpt_not_found":
            evidence_id = str(item.get("evidence_id", ""))
            findings.append(
                _finding(
                    "EV-12",
                    "blocker",
                    "证据摘录未在完整页面结果中找到。",
                    "修正摘录或重新采集来源正文。",
                    evidence_ids=[evidence_id] if evidence_id else [],
                )
            )
        elif rule_id == "citation_evidence_mismatch":
            evidence_ids = item.get("evidence_ids")
            evidence_ids = evidence_ids if isinstance(evidence_ids, list) else []
            findings.append(
                _finding(
                    "EV-05",
                    "blocker",
                    "可见引用链接与结构化证据绑定不一致。",
                    "使报告中的 citation 链接与 Claim 绑定的 EvidenceItem 一致。",
                    evidence_ids=[str(value) for value in evidence_ids],
                )
            )

    # EV-01、EV-02、EV-03、EV-05、EV-08、EV-09：逐条结论校验。
    for claim in claims:
        if not isinstance(claim, dict):
            findings.append(
                _finding("EV-10", "blocker", "存在非对象格式的 Claim。", "修正 Claim 结构。")
            )
            continue
        claim_id = claim.get("claim_id")
        text = str(claim.get("text", ""))
        claim_type = claim.get("claim_type")
        evidence_ids = claim.get("evidence_ids") if isinstance(claim.get("evidence_ids"), list) else []
        bound = [evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id]

        if claim_type == "current_fact" and any(
            marker in text for marker in HISTORICAL_NARRATIVE_MARKERS
        ):
            findings.append(
                _finding(
                    "EV-01",
                    "blocker",
                    "当前事实包含明显的历史时间叙述。",
                    "把该结论改为 historical_fact 并标明时间，或补充可证明当前状态的来源。",
                    claim_id,
                    evidence_ids,
                )
            )

        if claim.get("is_key") and claim_type != "review_question":
            if not evidence_ids or len(bound) != len(evidence_ids):
                findings.append(
                    _finding(
                        "EV-02",
                        "blocker",
                        "关键结论缺少有效的证据绑定。",
                        "补充可定位的 EvidenceItem，或删除该结论。",
                        claim_id,
                        evidence_ids,
                    )
                )

        if claim_type == "current_fact" and bound:
            has_eligible_source = any(
                _collection_status(item) in {"observed", "truncated"}
                if _is_live_evidence(item)
                else item.get("status") == "confirmed" and item.get("current_source")
                for item in bound
            )
            if not has_eligible_source:
                findings.append(
                    _finding(
                        "EV-01",
                        "blocker",
                        "当前事实只依赖历史或过期证据。",
                        "补充当前来源，或把结论明确改写为历史事实。",
                        claim_id,
                        evidence_ids,
                    )
                )

        if any(marker in text for marker in NEGATIVE_MARKERS):
            lower_excerpts = " ".join(str(item.get("excerpt", "")).lower() for item in bound)
            for group in CONTRADICTION_GROUPS:
                if any(term in text for term in group["claim_terms"]) and any(
                    term in lower_excerpts for term in group["evidence_terms"]
                ):
                    findings.append(
                        _finding(
                            "EV-03",
                            "blocker",
                            "否定性结论与已绑定证据摘录中的反例冲突。",
                            "展示反例并改写结论，不能把已披露内容写成未知。",
                            claim_id,
                            evidence_ids,
                        )
                    )
                    break

        if claim.get("is_key") and claim_type != "review_question" and evidence_ids:
            cited = claim.get("citation_evidence_ids")
            cited = cited if isinstance(cited, list) else []
            if not set(evidence_ids).issubset(set(cited)):
                findings.append(
                    _finding(
                        "EV-05",
                        "blocker",
                        "关键结论的可见引用未覆盖其证据绑定。",
                        "把每条关键结论直接绑定到对应 EvidenceItem。",
                        claim_id,
                        evidence_ids,
                    )
                )

        if claim_type == "review_question" and any(term in text for term in RISK_EVENT_TERMS):
            if not bound:
                findings.append(
                    _finding(
                        "EV-08",
                        "blocker",
                        "待复核问题包含没有证据支持的事件前提。",
                        "改写为中性问题，或补充该事件的直接来源。",
                        claim_id,
                        evidence_ids,
                    )
                )

        risky = [item for item in bound if _review_status(item) == "conflict"]
        if claim_type in {"current_fact", "historical_fact"} and risky:
            findings.append(
                _finding(
                    "EV-09",
                    "blocker",
                    "确定性事实使用了冲突证据。",
                    "并列展示冲突，或补充可支持该结论的 confirmed 证据。",
                    claim_id,
                    [str(item.get("evidence_id")) for item in risky],
                )
            )

    # EV-04：必填维度覆盖。
    required_dimensions = brief.get("required_dimensions")
    required_dimensions = required_dimensions if isinstance(required_dimensions, list) else []
    covered_dimensions = {
        claim.get("dimension") for claim in claims if isinstance(claim, dict) and claim.get("dimension")
    }
    missing_dimensions = sorted(set(required_dimensions) - covered_dimensions)
    if missing_dimensions:
        findings.append(
            _finding(
                "EV-04",
                "blocker",
                "缺少必填研究维度：" + "、".join(missing_dimensions),
                "补充对应 Claim；确实未知时也应显式记录未知及其证据。",
            )
        )

    rendered_text = report.get("rendered_text") if isinstance(report.get("rendered_text"), str) else ""
    actual_chars = len(rendered_text)
    searches = report.get("observed_searches") if isinstance(report.get("observed_searches"), int) else 0
    observed_urls = report.get("observed_page_urls")
    observed_urls = observed_urls if isinstance(observed_urls, list) else []
    used_tools = report.get("used_tools") if isinstance(report.get("used_tools"), list) else []

    alias_map = {}
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = canonicalize_url(str(item.get("source_url", "")))
        canonical = canonicalize_url(str(item.get("canonical_url", ""))) or source
        if source:
            alias_map[source] = canonical
    canonical_pages = []
    for url in observed_urls:
        normalized = canonicalize_url(str(url))
        canonical_pages.append(alias_map.get(normalized, normalized))
    unique_pages = len({url for url in canonical_pages if url})

    # EV-06：系统计算范围，不信任正文自报。
    limit_failures = []
    if isinstance(brief.get("max_chars"), int) and actual_chars > brief["max_chars"]:
        limit_failures.append(f"正文 {actual_chars} 字符，超过上限 {brief['max_chars']}")
    if isinstance(brief.get("max_searches"), int) and searches > brief["max_searches"]:
        limit_failures.append(f"搜索 {searches} 次，超过上限 {brief['max_searches']}")
    if isinstance(brief.get("max_pages"), int) and len(observed_urls) > brief["max_pages"]:
        limit_failures.append(f"页面查看 {len(observed_urls)} 次，超过上限 {brief['max_pages']}")
    forbidden = set(brief.get("forbidden_tools", [])) if isinstance(brief.get("forbidden_tools"), list) else set()
    forbidden_used = sorted(forbidden.intersection(used_tools))
    if forbidden_used:
        limit_failures.append("使用了禁用工具：" + "、".join(forbidden_used))
    allowed_domains = {
        str(domain).lower().strip(".")
        for domain in brief.get("allowed_domains", [])
        if isinstance(domain, str) and domain.strip(".")
    } if isinstance(brief.get("allowed_domains"), list) else set()
    disallowed_sources = []
    if allowed_domains:
        for item in evidence:
            if not isinstance(item, dict):
                continue
            hostname = urlsplit(str(item.get("source_url", ""))).hostname
            hostname = hostname.lower().strip(".") if hostname else ""
            if hostname and not any(
                hostname == domain or hostname.endswith("." + domain)
                for domain in allowed_domains
            ):
                disallowed_sources.append(str(item.get("evidence_id", hostname)))
    if disallowed_sources:
        limit_failures.append("证据来源超出允许域名：" + "、".join(sorted(disallowed_sources)))
    if limit_failures:
        findings.append(
            _finding(
                "EV-06",
                "blocker",
                "；".join(limit_failures),
                "按系统实际统计值缩减输出或重新执行受控任务。",
            )
        )
    self_reported = report.get("self_reported_chars")
    if isinstance(self_reported, int) and self_reported != actual_chars:
        findings.append(
            _finding(
                "EV-06",
                "warning",
                f"模型自报 {self_reported} 字符，系统实际为 {actual_chars}。",
                "界面和发布判断只采用系统实际统计值。",
            )
        )

    # EV-07：保留重复访问事实，同时给出规范化后的唯一来源数。
    if len(observed_urls) > unique_pages:
        findings.append(
            _finding(
                "EV-07",
                "warning",
                f"{len(observed_urls)} 次页面查看规范化后为 {unique_pages} 个唯一页面。",
                "合并重复来源，但不要抹去真实页面查看次数。",
            )
        )

    counts = Counter(item["severity"] for item in findings)
    human_review = audit.get("human_review")
    if counts["blocker"]:
        status = "blocked"
    elif human_review == "rejected":
        status = "rejected"
    elif human_review == "approved":
        status = "confirmed"
    else:
        status = "review_required"

    return {
        "task_id": brief.get("task_id"),
        "status": status,
        "metrics": {
            "actual_chars": actual_chars,
            "page_views": len(observed_urls),
            "unique_pages": unique_pages,
            "searches": searches,
        },
        "finding_counts": {
            "blocker": counts["blocker"],
            "warning": counts["warning"],
            "info": counts["info"],
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="离线研究证据校验器")
    parser.add_argument("input", type=Path, help="结构化样本 JSON")
    parser.add_argument("--output", type=Path, help="结果 JSON；省略时输出到终端")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    result_text = json.dumps(validate(payload), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result_text, encoding="utf-8")
    else:
        print(result_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
