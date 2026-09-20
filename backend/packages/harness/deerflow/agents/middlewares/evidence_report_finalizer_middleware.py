"""不调用模型地把证据提交工具结果转成最终可见 AI 消息。"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class EvidenceReportFinalizerMiddleware(AgentMiddleware):
    """在直接结束工具完成后，确定性追加同一份报告正文。"""

    @staticmethod
    def _finalize(state: AgentState, runtime: Runtime) -> dict | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        tool_message = messages[-1]
        if not isinstance(tool_message, ToolMessage):
            return None
        if tool_message.name != "submit_evidence_report":
            return None

        artifact = tool_message.artifact
        if not isinstance(artifact, Mapping):
            return None
        message_id = artifact.get("message_id")
        rendered_text = artifact.get("rendered_text")
        expected_message_id = f"evidence-report:{tool_message.tool_call_id}"
        if message_id != expected_message_id or not isinstance(rendered_text, str):
            return None
        if not rendered_text.strip():
            return None

        ai_message = AIMessage(content=rendered_text, id=message_id)
        context = getattr(runtime, "context", None) or {}
        journal = context.get("__run_journal")
        if journal is not None:
            try:
                journal.record_final_ai_message(ai_message)
            except Exception:
                logger.debug(
                    "Failed to record finalized evidence report message %s",
                    message_id,
                    exc_info=True,
                )
        return {"messages": [ai_message]}

    @override
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._finalize(state, runtime)

    @override
    async def aafter_agent(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._finalize(state, runtime)
