"""读取已完成 run 并持久化证据校验影子记录。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Literal

from app.gateway.evidence_validation.collector import collect_shadow_payload
from deerflow.evaluation.evidence_review_workflow import build_validation_record

logger = logging.getLogger(__name__)


def _raise_validator_error(_: dict) -> dict:
    raise RuntimeError("validator failed")


class ShadowValidationService:
    """只读已有运行事实；失败不得改变原运行状态或回答。"""

    def __init__(
        self,
        run_store: Any,
        event_store: Any,
        repository: Any,
        config_provider: Callable[[], Any],
        record_builder: Callable[..., dict] = build_validation_record,
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.repository = repository
        self.config_provider = config_provider
        self.record_builder = record_builder

    def _config(self) -> Any:
        provided = self.config_provider()
        return getattr(provided, "evidence_validation", provided)

    async def process_run(
        self,
        *,
        thread_id: str,
        run_id: str,
        owner_user_id: str,
        quality_profile_id: str | None = None,
        brief: dict | None = None,
        source: Literal["auto", "manual_replay"] = "auto",
    ) -> dict | None:
        if source not in {"auto", "manual_replay"}:
            raise ValueError("不支持的证据校验来源")

        run = await self.run_store.get(run_id, user_id=owner_user_id)
        if run is None or run.get("user_id") not in (None, owner_user_id):
            if source == "auto":
                return None
            raise LookupError("运行不存在")
        if run.get("thread_id") != thread_id:
            if source == "auto":
                return None
            raise LookupError("运行不存在")
        if run.get("status") != "success":
            return None

        metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
        if source == "auto":
            selected_profile = metadata.get("quality_profile_id")
            selected_brief = metadata.get("research_brief")
        else:
            selected_profile = quality_profile_id
            selected_brief = brief

        config = self._config()
        is_allowed = bool(
            config
            and hasattr(config, "is_allowed")
            and config.is_allowed(
                user_id=owner_user_id,
                quality_profile_id=selected_profile,
            )
        )
        if not is_allowed:
            if source == "auto":
                return None
            raise PermissionError("当前账号或质量配置未启用证据校验")
        if not isinstance(selected_brief, dict):
            if source == "auto":
                return None
            raise ValueError("手动重放必须提供 ResearchBrief")

        events = await self.event_store.list_events(
            thread_id,
            run_id,
            limit=500,
        )
        payload, semantic_state, message_id = collect_shadow_payload(
            run,
            events,
            brief=selected_brief,
            quality_profile_id=str(selected_profile),
            source=source,
        )
        record_kwargs = {
            "thread_id": thread_id,
            "run_id": run_id,
            "message_id": message_id,
            "owner_user_id": owner_user_id,
        }
        try:
            record = self.record_builder(payload, **record_kwargs)
        except Exception:
            logger.exception(
                "Evidence validation record builder failed for run %s; storing fail-closed result",
                run_id,
            )
            record = build_validation_record(
                payload,
                validator_func=_raise_validator_error,
                **record_kwargs,
            )

        record["quality_profile_id"] = str(selected_profile)
        record["semantic_evaluation"] = semantic_state
        return await self.repository.upsert(record)
