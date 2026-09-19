from __future__ import annotations

from pathlib import Path

import yaml

from deerflow.config.app_config import AppConfig
from deerflow.config.evidence_validation_config import EvidenceValidationConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_shadow_validation_is_disabled_by_default():
    config = EvidenceValidationConfig()

    assert config.enabled is False
    assert config.quality_profile_ids == ["evidence-research-v1"]
    assert config.allowed_user_ids == []
    assert config.is_allowed(user_id="u1", quality_profile_id="evidence-research-v1") is False


def test_requires_both_allowed_user_and_profile():
    config = EvidenceValidationConfig(
        enabled=True,
        allowed_user_ids=["u1"],
        quality_profile_ids=["evidence-research-v1"],
    )

    assert config.is_allowed(user_id="u1", quality_profile_id="evidence-research-v1") is True
    assert config.is_allowed(user_id="u2", quality_profile_id="evidence-research-v1") is False
    assert config.is_allowed(user_id="u1", quality_profile_id="ordinary-chat") is False
    assert config.is_allowed(user_id=None, quality_profile_id="evidence-research-v1") is False


def test_app_config_defaults_to_disabled_shadow_validation():
    config = AppConfig.model_validate(
        {"sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"}}
    )

    assert config.evidence_validation == EvidenceValidationConfig()


def test_example_config_is_version_15_and_does_not_allow_real_users():
    data = yaml.safe_load((REPO_ROOT / "config.example.yaml").read_text(encoding="utf-8"))

    assert data["config_version"] == 15
    assert data["evidence_validation"] == {
        "enabled": False,
        "quality_profile_ids": ["evidence-research-v1"],
        "allowed_user_ids": [],
    }