#!/usr/bin/env python3
"""把本地校验记录渲染为静态人工复核界面原型。"""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evidence_review_workflow import build_validation_record, submit_review


STATUS_META = {
    "blocked": ("不可发布", "danger"),
    "review_required": ("待人工复核", "warning"),
    "confirmed": ("已确认", "success"),
    "rejected": ("已驳回", "neutral"),
    "validator_error": ("校验异常", "neutral"),
}


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _render_claims(record: dict) -> str:
    claims = record.get("source_payload", {}).get("claims", [])
    if not claims:
        return '<p class="empty">暂无结构化陈述</p>'
    rows = []
    for claim in claims:
        rows.append(
            '<article class="evidence-row">'
            f'<div><span class="mono">{_text(claim.get("claim_id"))}</span>'
            f'<span class="dimension">{_text(claim.get("dimension"))}</span></div>'
            f'<p>{_text(claim.get("text"))}</p>'
            "</article>"
        )
    return "".join(rows)


def _render_evidence(record: dict) -> str:
    evidence = record.get("source_payload", {}).get("evidence", [])
    if not evidence:
        return '<p class="empty">暂无证据条目</p>'
    rows = []
    for item in evidence:
        url = _text(item.get("source_url"))
        rows.append(
            '<article class="evidence-row">'
            f'<div><strong>{_text(item.get("title"))}</strong>'
            f'<span class="evidence-status">{_text(item.get("status"))}</span></div>'
            f'<blockquote>{_text(item.get("excerpt"))}</blockquote>'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
            "</article>"
        )
    return "".join(rows)


def _render_findings(record: dict) -> str:
    findings = record.get("validation_result", {}).get("findings", [])
    if not findings:
        return '<div class="empty success-empty">未发现自动阻断项，等待人工复核。</div>'
    rows = []
    for finding in findings:
        severity = finding.get("severity", "info")
        rows.append(
            f'<article class="finding finding-{_text(severity)}">'
            f'<div><strong>{_text(finding.get("rule_id"))}</strong>'
            f'<span>{_text(severity)}</span></div>'
            f'<p>{_text(finding.get("message"))}</p>'
            f'<p class="action-copy">建议：{_text(finding.get("required_action"))}</p>'
            "</article>"
        )
    return "".join(rows)


def _reviewer_summary(record: dict) -> str:
    decisions = record.get("review_decisions", [])
    if not decisions:
        return "尚无人工决定"
    latest = decisions[-1]
    return (
        f"复核人：{_text(latest.get('reviewer_user_id'))} · "
        f"时间：{_text(latest.get('created_at'))}"
    )


def _render_record(record: dict, index: int) -> str:
    status = record.get("final_status", "validator_error")
    label, tone = STATUS_META.get(status, STATUS_META["validator_error"])
    validation = record.get("validation_result", {})
    metrics = validation.get("metrics", {})
    counts = validation.get("finding_counts", {})
    brief = record.get("source_payload", {}).get("brief", {})
    max_chars = brief.get("max_chars", "—")
    selected = " is-active" if index == 0 else ""
    hidden = "" if index == 0 else " hidden"
    approve_disabled = "" if status == "review_required" else " disabled aria-disabled=\"true\""

    return f"""
    <section class="review-case{selected}" data-case="case-{index}" data-status="{_text(status)}"{hidden}>
      <div class="status-card status-{tone}">
        <div>
          <p class="case-label">{_text(record.get("prototype_label", f"样本 {index + 1}"))}</p>
          <h2>证据校验：{label}</h2>
          <p class="status-subtitle">{counts.get("blocker", 0)} 阻断 · {counts.get("warning", 0)} 警告</p>
        </div>
        <div class="metrics" aria-label="系统统计">
          <span><strong>{metrics.get("actual_chars", 0)} / {max_chars}</strong> 字符</span>
          <span><strong>{metrics.get("page_views", 0)}</strong> 次查看 / <strong>{metrics.get("unique_pages", 0)}</strong> 个唯一页</span>
        </div>
      </div>

      <div class="review-grid">
        <section class="panel" aria-labelledby="claims-{index}">
          <h3 id="claims-{index}">报告陈述</h3>
          <div class="panel-scroll">{_render_claims(record)}</div>
        </section>
        <section class="panel" aria-labelledby="evidence-{index}">
          <h3 id="evidence-{index}">证据原文</h3>
          <div class="panel-scroll">{_render_evidence(record)}</div>
        </section>
        <section class="panel" aria-labelledby="findings-{index}">
          <h3 id="findings-{index}">校验发现</h3>
          <div class="panel-scroll">{_render_findings(record)}</div>
        </section>
        <section class="panel actions-panel" aria-labelledby="actions-{index}">
          <h3 id="actions-{index}">人工动作</h3>
          <p>{_reviewer_summary(record)}</p>
          <label for="reason-{index}">复核理由</label>
          <textarea id="reason-{index}" placeholder="退回或驳回时必须填写"></textarea>
          <div class="action-row">
            <button type="button" class="button button-primary" data-action="approve"{approve_disabled}>确认通过</button>
            <button type="button" class="button" data-action="return">退回修改</button>
            <button type="button" class="button button-quiet" data-action="reject">驳回</button>
          </div>
          <p class="prototype-feedback" role="status"></p>
        </section>
      </div>
    </section>
    """


def render_review_page(records: list[dict]) -> str:
    """渲染可离线打开的静态复核页面。"""
    if not records:
        raise ValueError("至少需要一条校验记录")

    tabs = "".join(
        f'<button type="button" class="case-tab{" is-active" if index == 0 else ""}" '
        f'data-target="case-{index}">{_text(record.get("prototype_label", f"样本 {index + 1}"))}</button>'
        for index, record in enumerate(records)
    )
    cases = "".join(_render_record(record, index) for index, record in enumerate(records))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>证据复核工作台｜B0 静态原型</title>
  <style>
    :root {{ color-scheme: light; --bg:#f5f7fa; --surface:#fff; --text:#172033; --muted:#667085; --line:#dfe4ea; --brand:#2958d6; --danger:#b42318; --danger-bg:#fff1f0; --warning:#8a4b08; --warning-bg:#fff8e8; --success:#157f3b; --success-bg:#eefbf3; --shadow:0 14px 40px rgba(23,32,51,.08); }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:"Segoe UI","Microsoft YaHei",sans-serif; font-size:14px; line-height:1.55; }}
    button, textarea {{ font:inherit; }}
    .shell {{ width:min(1500px, calc(100% - 40px)); margin:0 auto; padding:32px 0 48px; }}
    .page-header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:24px; margin-bottom:22px; }}
    .page-header h1 {{ margin:0 0 6px; font-size:28px; letter-spacing:-.03em; }}
    .page-header p {{ margin:0; color:var(--muted); }}
    .prototype-note {{ max-width:360px; padding:10px 14px; border:1px solid #cfd7e6; border-radius:10px; background:#fff; color:#475467; }}
    .tabs {{ display:flex; gap:8px; overflow:auto; margin-bottom:14px; padding-bottom:2px; }}
    .case-tab {{ flex:0 0 auto; border:1px solid var(--line); border-radius:9px; background:#fff; color:#475467; padding:9px 13px; cursor:pointer; }}
    .case-tab.is-active {{ border-color:var(--brand); background:#eef3ff; color:#173f9f; font-weight:600; }}
    .status-card {{ display:flex; justify-content:space-between; gap:24px; align-items:center; padding:22px 24px; border:1px solid var(--line); border-left-width:5px; border-radius:14px; background:var(--surface); box-shadow:var(--shadow); }}
    .status-danger {{ border-left-color:var(--danger); background:linear-gradient(90deg,var(--danger-bg),#fff 32%); }}
    .status-warning {{ border-left-color:#d97706; background:linear-gradient(90deg,var(--warning-bg),#fff 32%); }}
    .status-success {{ border-left-color:var(--success); background:linear-gradient(90deg,var(--success-bg),#fff 32%); }}
    .status-neutral {{ border-left-color:#667085; }}
    .case-label {{ margin:0 0 2px; color:var(--muted); font-size:12px; font-weight:600; letter-spacing:.04em; text-transform:uppercase; }}
    .status-card h2 {{ margin:0; font-size:22px; }}
    .status-subtitle {{ margin:3px 0 0; color:var(--muted); }}
    .metrics {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
    .metrics span {{ padding:8px 10px; border:1px solid rgba(102,112,133,.2); border-radius:8px; background:rgba(255,255,255,.7); color:#475467; }}
    .review-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; margin-top:14px; }}
    .panel {{ min-height:320px; border:1px solid var(--line); border-radius:14px; background:var(--surface); box-shadow:0 8px 28px rgba(23,32,51,.05); overflow:hidden; }}
    .panel h3 {{ margin:0; padding:15px 18px; border-bottom:1px solid var(--line); font-size:15px; }}
    .panel-scroll {{ max-height:380px; overflow:auto; padding:14px; }}
    .evidence-row {{ padding:12px; border:1px solid #e6e9ee; border-radius:10px; background:#fbfcfe; }}
    .evidence-row + .evidence-row {{ margin-top:9px; }}
    .evidence-row div {{ display:flex; align-items:center; justify-content:space-between; gap:10px; }}
    .evidence-row p, .evidence-row blockquote {{ margin:8px 0 0; }}
    .evidence-row blockquote {{ padding-left:10px; border-left:3px solid #cdd6ea; color:#475467; }}
    .evidence-row a {{ display:block; margin-top:8px; color:var(--brand); overflow-wrap:anywhere; }}
    .mono {{ font-family:Consolas,monospace; font-size:12px; color:#475467; }}
    .dimension, .evidence-status {{ padding:2px 7px; border-radius:999px; background:#eef2f6; color:#475467; font-size:11px; }}
    .finding {{ padding:12px; border-radius:10px; border:1px solid #e4e7ec; }}
    .finding + .finding {{ margin-top:9px; }}
    .finding div {{ display:flex; justify-content:space-between; gap:10px; }}
    .finding p {{ margin:6px 0 0; }}
    .finding-blocker {{ border-color:#f4c7c3; background:var(--danger-bg); }}
    .finding-warning {{ border-color:#f4d89c; background:var(--warning-bg); }}
    .action-copy {{ color:var(--muted); }}
    .empty {{ margin:0; padding:18px; color:var(--muted); text-align:center; }}
    .success-empty {{ border:1px dashed #a7d8b8; border-radius:10px; background:var(--success-bg); color:var(--success); }}
    .actions-panel {{ padding-bottom:16px; }}
    .actions-panel > p, .actions-panel > label, .actions-panel > textarea, .actions-panel > .action-row {{ margin-left:18px; margin-right:18px; }}
    .actions-panel label {{ display:block; margin-top:16px; margin-bottom:6px; color:#344054; font-weight:600; }}
    textarea {{ display:block; width:calc(100% - 36px); min-height:92px; resize:vertical; padding:10px; border:1px solid #cfd6df; border-radius:9px; color:var(--text); }}
    .action-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
    .button {{ border:1px solid #cfd6df; border-radius:8px; background:#fff; color:#344054; padding:9px 12px; cursor:pointer; }}
    .button-primary {{ border-color:var(--brand); background:var(--brand); color:#fff; }}
    .button-quiet {{ color:var(--danger); }}
    .button:disabled {{ cursor:not-allowed; opacity:.42; }}
    .prototype-feedback {{ min-height:22px; color:var(--muted); }}
    [hidden] {{ display:none !important; }}
    @media (max-width:820px) {{ .shell {{ width:min(100% - 24px,1500px); padding-top:18px; }} .page-header,.status-card {{ align-items:stretch; flex-direction:column; }} .metrics {{ justify-content:flex-start; }} .review-grid {{ grid-template-columns:1fr; }} .panel {{ min-height:0; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="page-header">
      <div><h1>证据复核工作台</h1><p>把“为什么不能发布”定位到具体陈述、证据与修改动作。</p></div>
      <div class="prototype-note"><strong>B0 静态原型，不会写入 DeerFlow</strong><br>所有数据来自本地固定夹具，不触发模型或网络请求。</div>
    </header>
    <nav class="tabs" aria-label="原型状态样本">{tabs}</nav>
    {cases}
  </main>
  <script>
    const tabs = document.querySelectorAll('.case-tab');
    const cases = document.querySelectorAll('.review-case');
    tabs.forEach((tab) => tab.addEventListener('click', () => {{
      tabs.forEach((item) => item.classList.remove('is-active'));
      cases.forEach((item) => {{ item.hidden = true; item.classList.remove('is-active'); }});
      tab.classList.add('is-active');
      const target = document.querySelector(`[data-case="${{tab.dataset.target}}"]`);
      target.hidden = false;
      target.classList.add('is-active');
    }}));
    document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => {{
      if (button.disabled) return;
      const panel = button.closest('.actions-panel');
      panel.querySelector('.prototype-feedback').textContent = '这是静态交互演示，不会提交或保存决定。';
    }}));
  </script>
</body>
</html>
"""


def _fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_prototype_records(fixtures_dir: Path) -> list[dict]:
    blocked = build_validation_record(
        _fixture(fixtures_dir / "t001_v3.json"),
        thread_id="prototype-blocked",
        run_id="prototype-blocked",
        message_id="prototype-blocked",
        owner_user_id="reviewer-1",
        now="2026-09-19T10:00:00+08:00",
    )
    blocked["prototype_label"] = "不可发布"

    pending = build_validation_record(
        _fixture(fixtures_dir / "b0_clean_current.json"),
        thread_id="prototype-pending",
        run_id="prototype-pending",
        message_id="prototype-pending",
        owner_user_id="reviewer-1",
        now="2026-09-19T10:00:00+08:00",
    )
    pending["prototype_label"] = "待人工复核"

    confirmed = submit_review(
        pending,
        actor_user_id="reviewer-1",
        decision="approved",
        expected_report_hash=pending["report_hash"],
        idempotency_key="prototype-approved",
        now="2026-09-19T10:03:00+08:00",
    )
    confirmed["prototype_label"] = "已确认"

    def broken_validator(_payload):
        raise RuntimeError("prototype simulated outage")

    error = build_validation_record(
        _fixture(fixtures_dir / "b0_clean_current.json"),
        thread_id="prototype-error",
        run_id="prototype-error",
        message_id="prototype-error",
        owner_user_id="reviewer-1",
        validator_func=broken_validator,
        now="2026-09-19T10:00:00+08:00",
    )
    error["prototype_label"] = "校验异常"
    return [blocked, pending, confirmed, error]


def main() -> int:
    parser = argparse.ArgumentParser(description="生成证据复核静态原型")
    parser.add_argument("--fixtures", type=Path, default=Path("tests/product/fixtures"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    html = render_review_page(build_prototype_records(args.fixtures))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
