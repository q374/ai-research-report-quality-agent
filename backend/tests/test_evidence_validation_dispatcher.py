"""任务完成后的证据校验影子调度器测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateway.evidence_validation.dispatcher import ShadowValidationDispatcher
from deerflow.runtime.runs.manager import RunRecord
from deerflow.runtime.runs.schemas import DisconnectMode, RunStatus


def success_record() -> RunRecord:
    return RunRecord(
        run_id="r1",
        thread_id="t1",
        assistant_id="lead_agent",
        status=RunStatus.success,
        on_disconnect=DisconnectMode.continue_,
        user_id="u1",
    )


@pytest.mark.anyio
async def test_dispatcher_does_not_delay_or_rewrite_completed_run():
    service = MagicMock()
    service.process_run = AsyncMock(return_value={"validation_id": "v1"})
    dispatcher = ShadowValidationDispatcher(service)
    record = success_record()
    record.task = asyncio.create_task(asyncio.sleep(0))

    dispatcher.schedule(record)

    assert record.status == RunStatus.success
    await dispatcher.drain()
    service.process_run.assert_awaited_once_with(
        thread_id="t1",
        run_id="r1",
        owner_user_id="u1",
        source="auto",
    )
    assert record.status == RunStatus.success


@pytest.mark.anyio
async def test_dispatcher_drains_before_database_close():
    gate = asyncio.Event()
    service = MagicMock()

    async def process_run(**_kwargs):
        await gate.wait()

    service.process_run = AsyncMock(side_effect=process_run)
    dispatcher = ShadowValidationDispatcher(service)
    record = success_record()
    record.task = asyncio.create_task(asyncio.sleep(0))
    dispatcher.schedule(record)
    await asyncio.sleep(0)

    gate.set()
    await dispatcher.drain(timeout=1.0)

    assert dispatcher.pending_count == 0


@pytest.mark.anyio
async def test_dispatcher_failure_is_isolated_from_run():
    service = MagicMock()
    service.process_run = AsyncMock(side_effect=RuntimeError("private failure"))
    dispatcher = ShadowValidationDispatcher(service)
    record = success_record()
    record.task = asyncio.create_task(asyncio.sleep(0))

    dispatcher.schedule(record)
    await dispatcher.drain()

    assert record.status == RunStatus.success
    assert dispatcher.pending_count == 0


@pytest.mark.anyio
async def test_dispatcher_skips_run_without_owner():
    service = MagicMock()
    service.process_run = AsyncMock()
    dispatcher = ShadowValidationDispatcher(service)
    record = success_record()
    record.user_id = None
    record.task = asyncio.create_task(asyncio.sleep(0))

    dispatcher.schedule(record)
    await dispatcher.drain()

    service.process_run.assert_not_awaited()
