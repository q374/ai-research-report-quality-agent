"""证据报告确定性收尾中间件测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from deerflow.agents.middlewares.evidence_report_finalizer_middleware import (
    EvidenceReportFinalizerMiddleware,
)


def report_tool_message(*, artifact: object | None = None) -> ToolMessage:
    return ToolMessage(
        content="Evidence report submitted",
        tool_call_id="tc-1",
        name="submit_evidence_report",
        artifact=artifact
        if artifact is not None
        else {
            "message_id": "evidence-report:tc-1",
            "rendered_text": "结论。[citation:来源1](https://example.com/doc)",
        },
    )


def test_after_agent_appends_same_report_as_ai_message() -> None:
    journal = Mock()
    runtime = SimpleNamespace(context={"__run_journal": journal})
    middleware = EvidenceReportFinalizerMiddleware()

    update = middleware.after_agent(
        {"messages": [report_tool_message()]},
        runtime,
    )

    assert update is not None
    ai_message = update["messages"][0]
    assert isinstance(ai_message, AIMessage)
    assert ai_message.id == "evidence-report:tc-1"
    assert ai_message.content.startswith("结论")
    journal.record_final_ai_message.assert_called_once_with(ai_message)


@pytest.mark.anyio
async def test_async_after_agent_matches_sync_result() -> None:
    runtime = SimpleNamespace(context={})
    middleware = EvidenceReportFinalizerMiddleware()

    update = await middleware.aafter_agent(
        {"messages": [report_tool_message()]},
        runtime,
    )

    assert update is not None
    assert update["messages"][0].id == "evidence-report:tc-1"


@pytest.mark.parametrize(
    "message",
    [
        ToolMessage(content="other", tool_call_id="tc-x", name="other_tool"),
        report_tool_message(artifact={}),
        report_tool_message(artifact={"message_id": "x", "rendered_text": 7}),
        AIMessage(content="already final"),
    ],
)
def test_after_agent_ignores_unrelated_or_malformed_messages(message) -> None:
    middleware = EvidenceReportFinalizerMiddleware()

    assert (
        middleware.after_agent(
            {"messages": [message]},
            SimpleNamespace(context={}),
        )
        is None
    )
