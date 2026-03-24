from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Awaitable


class RunCancelledError(Exception):
    """表示当前 agent 运行已被主动取消。"""


@dataclass
class RunCancellationContext:
    """
    单次 agent 运行的取消上下文。

    约束：
    - 只表示“本轮请求是否应停止继续执行”
    - 不承担错误语义；用户主动停止和连接断开都走同一套取消通道
    """

    reason: str = "请求已取消"
    _event: asyncio.Event | None = field(default=None, init=False, repr=False)

    def _get_event(self) -> asyncio.Event:
        if self._event is None:
            self._event = asyncio.Event()
        return self._event

    @property
    def is_cancelled(self) -> bool:
        return self._event is not None and self._event.is_set()

    def cancel(self, reason: str = "请求已取消") -> None:
        if self.is_cancelled:
            return
        self.reason = str(reason or "请求已取消")
        self._get_event().set()

    async def wait(self) -> None:
        await self._get_event().wait()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise RunCancelledError(self.reason)


async def await_with_cancellation(
    operation: Awaitable[Any],
    *,
    cancellation_context: RunCancellationContext | None = None,
    timeout: float | None = None,
) -> Any:
    """
    等待一个异步操作，同时响应取消信号和超时。

    行为：
    - 命中取消时，尽最大努力取消底层任务，并抛出 `RunCancelledError`
    - 命中超时时，取消底层任务，并抛出 `asyncio.TimeoutError`
    """

    operation_task = asyncio.create_task(operation)
    cancel_wait_task = None

    try:
        wait_set = {operation_task}
        if cancellation_context is not None:
            cancel_wait_task = asyncio.create_task(cancellation_context.wait())
            wait_set.add(cancel_wait_task)

        done, _pending = await asyncio.wait(
            wait_set,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if operation_task in done:
            return await operation_task

        if cancel_wait_task is not None and cancel_wait_task in done:
            operation_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await operation_task
            cancellation_context.raise_if_cancelled()

        operation_task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await operation_task
        raise asyncio.TimeoutError
    finally:
        if cancel_wait_task is not None:
            cancel_wait_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await cancel_wait_task
