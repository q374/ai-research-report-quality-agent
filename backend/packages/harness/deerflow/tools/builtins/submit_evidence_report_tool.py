"""将最终研究报告一次性提交为可见消息和持久证据事件。"""

from __future__ import annotations

import logging
from typing import Annotated

from langchain.tools import InjectedToolCallId, tool
from langchain_core.messages import ToolMessage

from deerflow.evaluation.evidence_submission import (
    ClaimCandidate,
    EvidenceCandidate,
    EvidenceReportSubmission,
)
from deerflow.tools.types import Runtime

logger = logging.getLogger(__name__)


@tool("submit_evidence_report", parse_docstring=True, return_direct=True)
def submit_evidence_report_tool(
    runtime: Runtime,
    rendered_text: str,
    claims: list[ClaimCandidate],
    evidence: list[EvidenceCandidate],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> ToolMessage:
    """提交最终研究报告，随后立即结束本次智能体运行。

    仅当报告正文、结论和证据已经全部准备好时调用。报告中的来源必须使用
    ``[citation:来源N](https://...)`` 格式；结论与证据关系仍是候选信息，
    不能由智能体自行标记为人工确认。

    Args:
        rendered_text: 展示给用户的完整 Markdown 报告正文。
        claims: 报告中的结构化结论候选列表。
        evidence: 支撑结论的结构化证据候选列表。

    Returns:
        携带已脱敏报告 artifact 的配对工具消息。最终 AI 消息由收尾中间件追加。
    """
    submission = EvidenceReportSubmission.model_validate(
        {
            "rendered_text": rendered_text,
            "claims": claims,
            "evidence": evidence,
        }
    )
    message_id = f"evidence-report:{tool_call_id}"
    payload = submission.to_event_payload(message_id)

    context = getattr(runtime, "context", None) or {}
    journal = context.get("__run_journal")
    if journal is not None:
        try:
            journal.record_evidence_report(payload, message_id=message_id)
        except Exception:
            logger.debug(
                "Failed to record evidence report event for message %s",
                message_id,
                exc_info=True,
            )

    return ToolMessage(
        content="Evidence report submitted",
        tool_call_id=tool_call_id,
        name="submit_evidence_report",
        artifact={
            "message_id": message_id,
            "rendered_text": submission.rendered_text,
        },
    )
