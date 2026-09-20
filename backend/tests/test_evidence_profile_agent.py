"""证据研究 Profile 的资格与 Lead Agent 注入测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deerflow.agents.lead_agent import agent as lead_agent_module
from deerflow.agents.middlewares.evidence_report_finalizer_middleware import (
    EvidenceReportFinalizerMiddleware,
)
from deerflow.config.app_config import AppConfig
from deerflow.config.evidence_validation_config import EvidenceValidationConfig
from deerflow.config.model_config import ModelConfig
from deerflow.config.sandbox_config import SandboxConfig
from deerflow.evaluation.evidence_profile import resolve_evidence_profile

ALLOWED_USER = "allowed-user-id"


def valid_brief() -> dict:
    return {
        "task_id": "T001",
        "required_dimensions": ["capability", "limitation"],
        "allowed_domains": ["example.com"],
        "time_scope": "current",
        "max_searches": 5,
        "max_pages": 8,
        "max_chars": 1200,
        "forbidden_tools": ["bash"],
    }


def make_app_config(*, enabled: bool = True) -> AppConfig:
    return AppConfig(
        models=[
            ModelConfig(
                name="fake-model",
                display_name="Fake",
                description=None,
                use="langchain_openai:ChatOpenAI",
                model="fake-model",
                supports_thinking=False,
                supports_vision=False,
            )
        ],
        sandbox=SandboxConfig(
            use="deerflow.sandbox.local:LocalSandboxProvider",
        ),
        evidence_validation=EvidenceValidationConfig(
            enabled=enabled,
            quality_profile_ids=["evidence-research-v1"],
            allowed_user_ids=[ALLOWED_USER],
        ),
    )


def run_config(
    *,
    user_id: str = ALLOWED_USER,
    profile: str | None = "evidence-research-v1",
    brief: dict | None = None,
    is_bootstrap: bool = False,
) -> dict:
    metadata = {}
    if profile is not None:
        metadata["quality_profile_id"] = profile
    if brief is not None:
        metadata["research_brief"] = brief
    return {
        "context": {"user_id": user_id, "is_bootstrap": is_bootstrap},
        "metadata": metadata,
    }


@pytest.mark.parametrize(
    ("user_id", "profile", "brief", "enabled", "expected"),
    [
        (ALLOWED_USER, "evidence-research-v1", valid_brief(), True, True),
        ("other-user", "evidence-research-v1", valid_brief(), True, False),
        (ALLOWED_USER, "other-profile", valid_brief(), True, False),
        (ALLOWED_USER, "evidence-research-v1", None, True, False),
        (ALLOWED_USER, "evidence-research-v1", valid_brief(), False, False),
    ],
)
def test_resolve_evidence_profile_qualification_matrix(
    user_id: str,
    profile: str,
    brief: dict | None,
    enabled: bool,
    expected: bool,
) -> None:
    resolved = resolve_evidence_profile(
        run_config(user_id=user_id, profile=profile, brief=brief),
        make_app_config(enabled=enabled),
    )

    assert (resolved is not None) is expected


@pytest.mark.parametrize(
    "brief_patch",
    [
        {"max_pages": -1},
        {"required_dimensions": "capability"},
        {"forbidden_tools": None},
    ],
)
def test_resolve_evidence_profile_rejects_invalid_brief_types(brief_patch: dict) -> None:
    brief = valid_brief()
    brief.update(brief_patch)

    assert resolve_evidence_profile(
        run_config(brief=brief),
        make_app_config(),
    ) is None


def _install_agent_fakes(monkeypatch, *, deferred_inputs: list[list] | None = None) -> None:
    import deerflow.tools as tools_module
    from deerflow.tools.builtins import tool_search as tool_search_module

    monkeypatch.setattr(tools_module, "get_available_tools", lambda **kwargs: [])
    monkeypatch.setattr(
        lead_agent_module,
        "_load_enabled_skills_for_tool_policy",
        lambda available_skills, *, app_config: [],
    )
    monkeypatch.setattr(
        lead_agent_module,
        "create_chat_model",
        lambda **kwargs: "fake-model",
    )
    monkeypatch.setattr(lead_agent_module, "build_tracing_callbacks", lambda: [])
    monkeypatch.setattr(lead_agent_module, "load_agent_config", lambda _: None)
    monkeypatch.setattr(
        lead_agent_module,
        "build_middlewares",
        lambda *args, custom_middlewares=None, **kwargs: list(custom_middlewares or []),
    )
    monkeypatch.setattr(
        lead_agent_module,
        "apply_prompt_template",
        lambda **kwargs: "BASE_PROMPT",
    )
    monkeypatch.setattr(lead_agent_module, "create_agent", lambda **kwargs: kwargs)

    def fake_assemble(tools, *, enabled):
        if deferred_inputs is not None:
            deferred_inputs.append(list(tools))
        return list(tools), SimpleNamespace(deferred_names=set())

    monkeypatch.setattr(tool_search_module, "assemble_deferred_tools", fake_assemble)


def test_allowed_profile_injects_tool_middleware_and_static_prompt(monkeypatch) -> None:
    deferred_inputs: list[list] = []
    _install_agent_fakes(monkeypatch, deferred_inputs=deferred_inputs)

    result = lead_agent_module._make_lead_agent(
        run_config(brief=valid_brief()),
        app_config=make_app_config(),
    )

    assert [tool.name for tool in result["tools"]] == ["submit_evidence_report"]
    assert not any(
        tool.name == "submit_evidence_report"
        for tool in deferred_inputs[0]
    )
    assert any(
        isinstance(middleware, EvidenceReportFinalizerMiddleware)
        for middleware in result["middleware"]
    )
    assert "仅在完成研究后调用 submit_evidence_report 一次" in result["system_prompt"]
    assert "[citation:来源N](URL)" in result["system_prompt"]
    assert ALLOWED_USER not in result["system_prompt"]


@pytest.mark.parametrize(
    "config",
    [
        run_config(user_id="other-user", brief=valid_brief()),
        run_config(profile="other-profile", brief=valid_brief()),
        run_config(brief=None),
        run_config(brief=valid_brief(), is_bootstrap=True),
        {"context": {"user_id": ALLOWED_USER}, "metadata": {}},
    ],
)
def test_ineligible_or_bootstrap_agent_gets_no_finalizer_pair(
    monkeypatch,
    config: dict,
) -> None:
    _install_agent_fakes(monkeypatch)

    result = lead_agent_module._make_lead_agent(
        config,
        app_config=make_app_config(),
    )

    assert all(tool.name != "submit_evidence_report" for tool in result["tools"])
    assert not any(
        isinstance(middleware, EvidenceReportFinalizerMiddleware)
        for middleware in result["middleware"]
    )
    assert "submit_evidence_report" not in result["system_prompt"]
