"""
独立进程工具执行器。

设计边界：
- 只负责把单个工具调用放到独立子进程中执行
- 只提供“启动 / 轮询结果 / 强制终止”能力
- 不承担工具选择、超时策略和消息封装
"""

from __future__ import annotations

import asyncio
import multiprocessing
from contextlib import suppress
from dataclasses import dataclass
from queue import Empty
from time import perf_counter
from typing import Any, Callable

from nexus.config.logger import get_logger

logger = get_logger(__name__)

PROCESS_RESULT_POLL_INTERVAL_SECONDS = 0.05
PROCESS_JOIN_TIMEOUT_SECONDS = 1.0


def _run_process_target(
    process_target: Callable[[dict[str, Any]], Any],
    tool_args: dict[str, Any],
    result_queue: multiprocessing.Queue,
) -> None:
    try:
        result_queue.put(("success", process_target(tool_args)))
    except Exception as error:  # noqa: BLE001 - 子进程边界统一回传异常文本
        result_queue.put(("error", str(error)))


@dataclass
class IsolatedToolProcessRunner:
    """
    单个工具调用的子进程运行句柄。

    该对象只服务一次执行。
    """

    process_target: Callable[[dict[str, Any]], Any]
    tool_args: dict[str, Any]
    tool_name: str

    def __post_init__(self) -> None:
        self._process: multiprocessing.Process | None = None
        self._result_queue: multiprocessing.Queue | None = None

    def _cleanup_queue(self) -> None:
        if self._result_queue is None:
            return
        with suppress(Exception):
            self._result_queue.close()
        with suppress(Exception):
            self._result_queue.join_thread()
        self._result_queue = None

    def _close_process(self) -> None:
        if self._process is None:
            return
        if self._process.is_alive():
            return
        with suppress(Exception):
            self._process.close()
        self._process = None

    def _terminate_process(self) -> None:
        if self._process is None:
            return
        if not self._process.is_alive():
            self._close_process()
            return

        self._process.terminate()
        self._process.join(PROCESS_JOIN_TIMEOUT_SECONDS)
        if self._process.is_alive():
            kill_process = getattr(self._process, "kill", None)
            if callable(kill_process):
                kill_process()
                self._process.join(PROCESS_JOIN_TIMEOUT_SECONDS)
        if self._process.is_alive():
            logger.error("[隔离工具进程终止失败] tool=%s", self.tool_name)
        else:
            logger.info("[隔离工具进程已终止] tool=%s", self.tool_name)
        self._close_process()

    async def run(self) -> Any:
        context = multiprocessing.get_context("spawn")
        self._result_queue = context.Queue()
        self._process = context.Process(
            target=_run_process_target,
            args=(self.process_target, self.tool_args, self._result_queue),
            daemon=True,
        )
        self._process.start()

        try:
            while True:
                try:
                    status, payload = self._result_queue.get_nowait()
                except Empty:
                    if self._process is not None and not self._process.is_alive():
                        raise RuntimeError(f"isolated tool process exited without result: {self.tool_name}")
                    await asyncio.sleep(PROCESS_RESULT_POLL_INTERVAL_SECONDS)
                    continue

                if status == "success":
                    return payload
                raise RuntimeError(str(payload))
        finally:
            if self._process is not None:
                self._process.join(PROCESS_JOIN_TIMEOUT_SECONDS)
            self._close_process()
            self._cleanup_queue()

    def cancel(self) -> None:
        started_at = perf_counter()
        self._terminate_process()
        logger.info(
            "[隔离工具取消结束] tool=%s elapsed_ms=%d",
            self.tool_name,
            int(max(0, (perf_counter() - started_at) * 1000)),
        )
        self._cleanup_queue()
