"""证据研究 Profile 的资格解析与静态提示。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from deerflow.config.app_config import AppConfig

EVIDENCE_PROFILE_PROMPT_SUFFIX = """

<evidence_research_profile>
仅在完成研究后调用 submit_evidence_report 一次；rendered_text 是用户最终看到的 Markdown。
重要结论使用 [citation:来源N](URL)；Claim/Evidence 只表达候选关系，不得声明人工 confirmed。
</evidence_research_profile>
"""


class ResearchBriefContract(BaseModel):
    """与现有证据重放 API 一致的研究任务边界。"""

    model_config = ConfigDict(extra="ignore")

    task_id: str
    required_dimensions: list[str]
    allowed_domains: list[str]
    time_scope: str
    max_searches: int = Field(ge=0)
    max_pages: int = Field(ge=0)
    max_chars: int = Field(ge=0)
    forbidden_tools: list[str]


@dataclass(frozen=True, slots=True)
class EvidenceProfileContext:
    """已通过账号、Profile 和 ResearchBrief 三重门禁的上下文。"""

    quality_profile_id: str
    research_brief: dict[str, Any]
    prompt_suffix: str = EVIDENCE_PROFILE_PROMPT_SUFFIX


def resolve_evidence_profile(
    config: RunnableConfig,
    app_config: AppConfig,
) -> EvidenceProfileContext | None:
    """只为可信账号和完整证据研究配置返回 finalizer 上下文。"""
    context = config.get("context", {}) or {}
    metadata = config.get("metadata", {}) or {}
    if not isinstance(context, Mapping) or not isinstance(metadata, Mapping):
        return None

    user_id = context.get("user_id")
    quality_profile_id = metadata.get("quality_profile_id")
    if not isinstance(user_id, str) or not isinstance(quality_profile_id, str):
        return None
    if not app_config.evidence_validation.is_allowed(
        user_id=user_id,
        quality_profile_id=quality_profile_id,
    ):
        return None

    raw_brief = metadata.get("research_brief")
    if not isinstance(raw_brief, Mapping):
        return None
    try:
        brief = ResearchBriefContract.model_validate(dict(raw_brief))
    except ValidationError:
        return None

    return EvidenceProfileContext(
        quality_profile_id=quality_profile_id,
        research_brief=brief.model_dump(mode="json"),
    )
