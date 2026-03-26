from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

from nexus.core.agent_runtime.cancellation import RunCancellationContext
from nexus.config.logger import get_logger


ACTIVE_RUN_FINISHED_TTL_SECONDS = 300
logger = get_logger(__name__)
RunKey = tuple[str, str]


@dataclass
class ActiveRunEntry:
    """单次活跃运行的注册信息。"""

    session_id: str
    request_id: str
    cancellation_context: RunCancellationContext


@dataclass
class FinishedRunEntry:
    """最近结束运行的只读摘要，用于取消接口区分 `already_finished`。"""

    session_id: str
    request_id: str
    status: str
    finished_at: float


@dataclass(frozen=True)
class CancelRunResult:
    """显式取消请求的即时结果。"""

    status: str
    accepted: bool


class ActiveRunRegistry:
    """
    进程内活跃运行注册表。

    设计边界：
    - 维护活跃运行到取消上下文的映射
    - 维护短期已结束运行摘要，便于取消接口返回明确状态
    - 取消接口只负责投递取消信号，不等待清理完成
    - 真正的停止完成由运行链路自己的清理日志确认
    """

    def __init__(self) -> None:
        # 复合键：避免不同 session 间 request_id 冲突导致串话。
        self._entries: dict[RunKey, ActiveRunEntry] = {}
        self._finished_entries: dict[RunKey, FinishedRunEntry] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _build_key(session_id: str, request_id: str) -> RunKey:
        normalized_session_id = str(session_id or "").strip()
        normalized_request_id = str(request_id or "").strip()
        return normalized_session_id, normalized_request_id

    def _prune_finished_entries(self) -> None:
        now = monotonic()
        expired_keys = [
            key
            for key, entry in self._finished_entries.items()
            if now - entry.finished_at > ACTIVE_RUN_FINISHED_TTL_SECONDS
        ]
        for key in expired_keys:
            self._finished_entries.pop(key, None)

    async def register(
        self,
        *,
        session_id: str,
        request_id: str,
        cancellation_context: RunCancellationContext,
    ) -> None:
        async with self._lock:
            self._prune_finished_entries()
            key = self._build_key(session_id, request_id)
            self._entries[key] = ActiveRunEntry(
                session_id=session_id,
                request_id=request_id,
                cancellation_context=cancellation_context,
            )
            # 支持“同 request_id 复用重试”：新注册覆盖旧完成态，避免被误判为 already_finished。
            self._finished_entries.pop(key, None)

    async def mark_finished(self, *, session_id: str, request_id: str, status: str) -> None:
        async with self._lock:
            self._prune_finished_entries()
            key = self._build_key(session_id, request_id)
            entry = self._entries.pop(key, None)
            if entry is None:
                return
            self._finished_entries[key] = FinishedRunEntry(
                session_id=entry.session_id,
                request_id=entry.request_id,
                status=status,
                finished_at=monotonic(),
            )

    async def cancel(
        self,
        *,
        session_id: str,
        request_id: str,
        reason: str,
    ) -> CancelRunResult:
        async with self._lock:
            self._prune_finished_entries()
            key = self._build_key(session_id, request_id)

            finished_entry = self._finished_entries.get(key)
            if finished_entry is not None:
                logger.info(
                    "[取消会话未命中活跃运行] session_id=%s request_id=%s status=already_finished",
                    session_id,
                    request_id,
                )
                return CancelRunResult(
                    status="already_finished",
                    accepted=False,
                )

            entry = self._entries.get(key)
            if entry is None:
                logger.warning(
                    "[取消会话未命中活跃运行] session_id=%s request_id=%s status=not_found",
                    session_id,
                    request_id,
                )
                return CancelRunResult(
                    status="not_found",
                    accepted=False,
                )

            logger.info(
                "[取消会话命中活跃运行] session_id=%s request_id=%s",
                session_id,
                request_id,
            )
            entry.cancellation_context.cancel(reason)
            return CancelRunResult(
                status="accepted",
                accepted=True,
            )


active_run_registry = ActiveRunRegistry()
