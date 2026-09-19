"""在主任务完成后异步运行证据校验，不阻塞或改写主任务。"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deerflow.runtime.runs.manager import RunRecord

logger = logging.getLogger(__name__)


class ShadowValidationDispatcher:
    def __init__(self, service: Any) -> None:
        self.service = service
        self._tasks: set[asyncio.Task[None]] = set()

    @property
    def pending_count(self) -> int:
        return len(self._tasks)

    def schedule(self, record: RunRecord) -> None:
        """安排旁路校验；没有任务或所有者时安全跳过。"""
        if record.task is None or not record.user_id:
            return
        task = asyncio.create_task(self._after_run(record))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _after_run(self, record: RunRecord) -> None:
        try:
            await asyncio.shield(record.task)
        except asyncio.CancelledError:
            return
        except Exception:
            # 主任务失败由原生命周期负责；影子流程不重复改写状态。
            return

        try:
            await self.service.process_run(
                thread_id=record.thread_id,
                run_id=record.run_id,
                owner_user_id=str(record.user_id),
                source="auto",
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Evidence validation shadow task failed for run %s",
                record.run_id,
            )

    async def drain(self, timeout: float = 5.0) -> None:
        """有界等待旁路任务，超时仅取消旁路，不取消主任务。"""
        tasks = list(self._tasks)
        if not tasks:
            return
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
