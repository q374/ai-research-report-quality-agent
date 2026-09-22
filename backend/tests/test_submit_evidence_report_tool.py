"""证据报告直接结束工具测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from _agent_e2e_helpers import FakeToolCallingModel
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import PrivateAttr, ValidationError

from deerflow.agents.middlewares.evidence_report_finalizer_middleware import (
    EvidenceReportFinalizerMiddleware,
)
from deerflow.evaluation.evidence_submission import sanitize_citation_links
from deerflow.tools.builtins.submit_evidence_report_tool import (
    submit_evidence_report_tool,
)


def make_claim(claim_id: str) -> dict:
    return {
        "claim_id": claim_id,
        "text": "这是有来源支持的结论",
        "claim_type": "current_fact",
        "dimension": "capability",
        "is_key": True,
        "evidence_ids": ["E1"],
        "citation_evidence_ids": ["E1"],
    }


def make_evidence(evidence_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "source_url": "https://example.com/doc?token=secret&id=7",
        "title": "来源标题",
        "published_at": None,
        "excerpt": "来源原文摘要",
        "proposed_relation": "supports",
    }


def tool_args() -> dict:
    return {
        "rendered_text": ("结论。[citation:来源1](https://example.com/doc?api_key=secret&id=7)"),
        "claims": [make_claim("C1")],
        "evidence": [make_evidence("E1")],
    }


def test_tool_call_schema_exposes_structured_claim_and_evidence_fields() -> None:
    schema = convert_to_openai_tool(submit_evidence_report_tool)["function"]["parameters"]
    claim_definition = schema["properties"]["claims"]["items"]
    evidence_definition = schema["properties"]["evidence"]["items"]

    assert set(claim_definition["required"]) == {
        "claim_id",
        "text",
        "claim_type",
        "dimension",
        "is_key",
        "evidence_ids",
        "citation_evidence_ids",
    }
    assert set(evidence_definition["required"]) == {
        "evidence_id",
        "source_url",
        "title",
        "excerpt",
        "proposed_relation",
    }


def test_submit_tool_returns_terminal_tool_message_and_records_event() -> None:
    journal = Mock()
    runtime = SimpleNamespace(context={"__run_journal": journal})

    tool_message = submit_evidence_report_tool.func(
        runtime=runtime,
        tool_call_id="tc-1",
        **tool_args(),
    )

    assert isinstance(tool_message, ToolMessage)
    assert tool_message.name == "submit_evidence_report"
    assert tool_message.artifact["message_id"] == "evidence-report:tc-1"
    assert tool_message.artifact["rendered_text"].startswith("结论")
    assert "secret" not in tool_message.artifact["rendered_text"]
    journal.record_evidence_report.assert_called_once()


def test_submit_tool_without_journal_still_returns_report_artifact() -> None:
    runtime = SimpleNamespace(context={})

    tool_message = submit_evidence_report_tool.func(
        runtime=runtime,
        tool_call_id="tc-2",
        **tool_args(),
    )

    assert isinstance(tool_message, ToolMessage)
    assert tool_message.artifact["rendered_text"].startswith("结论")


def test_invalid_submission_does_not_write_event() -> None:
    journal = Mock()
    runtime = SimpleNamespace(context={"__run_journal": journal})
    invalid = tool_args()
    invalid["evidence"][0]["status"] = "confirmed"

    with pytest.raises(ValidationError):
        submit_evidence_report_tool.func(
            runtime=runtime,
            tool_call_id="tc-invalid",
            **invalid,
        )

    journal.record_evidence_report.assert_not_called()


class CountingFakeToolCallingModel(FakeToolCallingModel):
    """记录真实 agent 图调用模型的次数。"""

    _invocation_count: int = PrivateAttr(default=0)

    @property
    def invocation_count(self) -> int:
        return self._invocation_count

    def _generate(self, *args, **kwargs):
        self._invocation_count += 1
        return super()._generate(*args, **kwargs)


def test_return_direct_with_finalizer_finishes_after_one_model_invocation() -> None:
    rendered_text = sanitize_citation_links(tool_args()["rendered_text"])
    model = CountingFakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "submit_evidence_report",
                        "args": tool_args(),
                        "id": "tc-e2e-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    graph = create_agent(
        model=model,
        tools=[submit_evidence_report_tool],
        middleware=[EvidenceReportFinalizerMiddleware()],
    )

    result = graph.invoke(
        {"messages": [("user", "请生成带来源的报告")]},
        context={},
    )

    assert model.invocation_count == 1
    assert result["messages"][-1].type == "ai"
    assert result["messages"][-1].content == rendered_text
    assert [message.type for message in result["messages"][-2:]] == ["tool", "ai"]
