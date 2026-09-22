"""证据校验影子运行配置。"""

from pydantic import BaseModel, Field


class EvidenceValidationConfig(BaseModel):
    """限制影子校验只作用于显式允许的账号和质量配置。"""

    enabled: bool = False
    quality_profile_ids: list[str] = Field(default_factory=lambda: ["evidence-research-v1"])
    allowed_user_ids: list[str] = Field(default_factory=list)

    def is_allowed(
        self,
        *,
        user_id: str | None,
        quality_profile_id: str | None,
    ) -> bool:
        return bool(self.enabled and user_id and user_id in self.allowed_user_ids and quality_profile_id and quality_profile_id in self.quality_profile_ids)
