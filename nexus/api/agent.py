from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from nexus.core.agent_runtime import RunCancellationContext, RunCancelledError
from nexus.core.schemas import ChatRequestContext
from nexus.services.agent_service import AgentService
from nexus.common.dependencies import get_agent_service
from nexus.config.logger import get_logger, reset_log_session_id, set_log_session_id
from nexus.services.auth_service import check_login
from nexus.common.exceptions import ParmasValidationError, AuthError

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])
SSE_RESPONSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


REQUEST_DISCONNECT_POLL_INTERVAL_SECONDS = 0.1


async def _monitor_request_disconnect(
    request: Request,
    cancellation_context: RunCancellationContext,
) -> None:
    while not cancellation_context.is_cancelled:
        if await request.is_disconnected():
            cancellation_context.cancel("客户端已断开连接")
            return
        await asyncio.sleep(REQUEST_DISCONNECT_POLL_INTERVAL_SECONDS)


async def _safe_stream(
    stream: AsyncGenerator[str, None],
    session_id: str,
    *,
    request: Request | None = None,
    cancellation_context: RunCancellationContext | None = None,
) -> AsyncGenerator[str, None]:
    """包装流式输出，确保异常被记录并转换为 SSE 错误事件。"""
    token = set_log_session_id(session_id)
    disconnect_task = None
    if request is not None and cancellation_context is not None:
        disconnect_task = asyncio.create_task(_monitor_request_disconnect(request, cancellation_context))
    try:
        async for chunk in stream:
            yield chunk
    except RunCancelledError:
        logger.info("[SSE 会话取消] session_id=%s", session_id)
    except Exception as exc:
        logger.exception("Streaming response error")
        payload = {"type": "error", "message": f"Streaming error: {str(exc)}"}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    finally:
        if disconnect_task is not None:
            disconnect_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await disconnect_task
        reset_log_session_id(token)

@router.post("/chat/completions")
async def chat_completions(
    context: ChatRequestContext,
    request: Request,
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    统一的智能体对话接口 
    支持流式响应
    根据 context.mode ("chat" | "builder" | "debugger") 分流处理不同智能体类型的请求。
    """
    context.auth_token = request.headers.get("Authorization")
    # 登录校验
    if not context.auth_token:
        raise AuthError("Authorization token is required")
    if not check_login(context.auth_token):
        raise AuthError("Current user is not logged in")

    # 校验 mode 是否有效
    if context.mode not in ["chat", "builder", "debugger"]:
        logger.error("Invalid agent mode: %s", context.mode)
        raise ParmasValidationError(f"Invalid agent mode: {context.mode}")

    # Chat 模式需要模型配置；Builder / Debugger 当前为禁用入口，由后端返回固定提示。
    if context.mode == "chat" and not context.model_config_id:
        raise ParmasValidationError("model_config_id is required")
    
    # 去除首尾空格；用户至少要提供自然语言或 execution_hints 其中之一。
    context.user_prompt = context.user_prompt.strip() if context.user_prompt else ""
    if not context.user_prompt and not context.execution_hints.has_items():
        raise ParmasValidationError("user_prompt is required")
    
    # 校验 session_id 是否存在
    if not context.session_id:
        raise ParmasValidationError("session_id is required")

    token = set_log_session_id(context.session_id)
    try:
        logger.info(
            "[收到用户请求] agent=%s user_prompt=%s execution_hints=%s",
            context.mode,
            context.user_prompt,
            json.dumps(context.execution_hints.summary(), ensure_ascii=False, sort_keys=True),
        )
        cancellation_context = RunCancellationContext()

        # Chat Agent
        if context.mode == "chat":
            return StreamingResponse(
                _safe_stream(
                    agent_service.handle_chat_request_with_cancellation(
                        context,
                        cancellation_context=cancellation_context,
                    ),
                    context.session_id,
                    request=request,
                    cancellation_context=cancellation_context,
                ),
                media_type="text/event-stream",
                headers=SSE_RESPONSE_HEADERS,
            )

        # Builder Agent
        if context.mode == "builder":
            return StreamingResponse(
                _safe_stream(agent_service.handle_builder_request(context), context.session_id),
                media_type="text/event-stream",
                headers=SSE_RESPONSE_HEADERS,
            )

        # Debugger Agent
        return StreamingResponse(
            _safe_stream(agent_service.handle_debugger_request(context), context.session_id),
            media_type="text/event-stream",
            headers=SSE_RESPONSE_HEADERS,
        )
    finally:
        reset_log_session_id(token)
