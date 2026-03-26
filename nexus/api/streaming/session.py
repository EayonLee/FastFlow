from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import Any, AsyncGenerator

from fastapi import Request

from nexus.config.logger import get_logger, reset_log_session_id, set_log_session_id
from nexus.core.agent_runtime import RunCancellationContext, RunCancelledError, active_run_registry


logger = get_logger(__name__)
REQUEST_DISCONNECT_POLL_INTERVAL_SECONDS = 0.1
TERMINAL_EVENT_TYPES = {"run.completed", "error"}


async def monitor_request_disconnect(
    request: Request,
    cancellation_context: RunCancellationContext,
) -> None:
    """把 HTTP 连接断开转换成运行时取消信号。"""
    while not cancellation_context.is_cancelled:
        if await request.is_disconnected():
            cancellation_context.cancel("客户端已断开连接")
            return
        await asyncio.sleep(REQUEST_DISCONNECT_POLL_INTERVAL_SECONDS)


def _build_sse_data_event(payload: dict[str, Any]) -> dict[str, str]:
    """将业务事件编码为 SSE `data` 字段。"""
    return {"data": json.dumps(payload, ensure_ascii=False)}


def _resolve_cancel_status(cancellation_context: RunCancellationContext | None) -> str:
    """根据取消原因区分用户取消和连接断开。"""
    if cancellation_context is None:
        return "cancelled"
    reason = str(cancellation_context.reason or "").strip()
    if "断开连接" in reason:
        return "disconnected"
    return "cancelled"


async def safe_stream(
    stream: AsyncGenerator[dict[str, Any], None],
    session_id: str,
    *,
    request_id: str | None = None,
    request: Request | None = None,
    cancellation_context: RunCancellationContext | None = None,
) -> AsyncGenerator[dict[str, str], None]:
    """
    包装 SSE 业务流，补齐取消监控、终态归类和清理日志。

    终态规则（不兼容历史协议）：
    - `run.completed` -> `completed`
    - `error` -> `failed`
    - 取消/断连 -> `cancelled` / `disconnected`
    - 无终态直接结束 -> 强制 `failed` + 补发标准 `error` 事件
    """
    token = set_log_session_id(session_id)
    disconnect_task = None
    finish_status = "running"
    end_reason = ""
    terminal_event_seen = False

    if request is not None and cancellation_context is not None:
        disconnect_task = asyncio.create_task(monitor_request_disconnect(request, cancellation_context))

    try:
        async for event in stream:
            if not isinstance(event, dict):
                raise TypeError(f"invalid stream event type: {type(event)}")

            event_type = str(event.get("type") or "").strip()
            if event_type in TERMINAL_EVENT_TYPES:
                if terminal_event_seen:
                    logger.warning(
                        "[SSE 协议错误] session_id=%s request_id=%s reason=duplicate_terminal_event event_type=%s",
                        session_id,
                        request_id or "",
                        event_type,
                    )
                else:
                    terminal_event_seen = True
                    if event_type == "run.completed":
                        finish_status = "completed"
                        end_reason = "run_completed"
                    else:
                        finish_status = "failed"
                        end_reason = "error_event"

            yield _build_sse_data_event(event)

        if finish_status == "running":
            finish_status = "failed"
            end_reason = "missing_terminal_event"
            terminal_event_seen = True
            logger.warning(
                "[SSE 协议错误] session_id=%s request_id=%s reason=missing_terminal_event",
                session_id,
                request_id or "",
            )
            yield _build_sse_data_event(
                {
                    "type": "error",
                    "message": "SSE 会话缺少终态事件(run.completed/error)",
                }
            )
    except RunCancelledError:
        finish_status = _resolve_cancel_status(cancellation_context)
        end_reason = "cancellation_signal"
        logger.info(
            "[SSE 会话取消] session_id=%s request_id=%s status=%s reason=%s",
            session_id,
            request_id or "",
            finish_status,
            cancellation_context.reason if cancellation_context is not None else "",
        )
    except asyncio.CancelledError:
        finish_status = (
            _resolve_cancel_status(cancellation_context)
            if cancellation_context is not None and cancellation_context.is_cancelled
            else "disconnected"
        )
        end_reason = "stream_task_cancelled"
        logger.info(
            "[SSE 会话取消] session_id=%s request_id=%s status=%s reason=%s",
            session_id,
            request_id or "",
            finish_status,
            cancellation_context.reason if cancellation_context is not None else "",
        )
    except Exception as exc:
        if terminal_event_seen and finish_status in {"completed", "failed"}:
            # 终态事件已经发出后，传输层异常不应篡改业务终态。
            end_reason = "stream_exception_after_terminal"
            logger.warning(
                "[SSE 终态后传输异常] session_id=%s request_id=%s status=%s error=%s",
                session_id,
                request_id or "",
                finish_status,
                str(exc),
                exc_info=True,
            )
        else:
            finish_status = "failed"
            end_reason = "stream_exception"
            logger.exception("Streaming response error")
            if not terminal_event_seen:
                yield _build_sse_data_event({"type": "error", "message": f"Streaming error: {str(exc)}"})
    finally:
        if finish_status == "running":
            finish_status = "failed"
            end_reason = end_reason or "missing_terminal_event"

        if request_id:
            await active_run_registry.mark_finished(
                session_id=session_id,
                request_id=request_id,
                status=finish_status,
            )
            logger.info(
                "[SSE 会话终态] session_id=%s request_id=%s status=%s end_reason=%s",
                session_id,
                request_id,
                finish_status,
                end_reason or "unknown",
            )

        if disconnect_task is not None:
            disconnect_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await disconnect_task

        reset_log_session_id(token)
