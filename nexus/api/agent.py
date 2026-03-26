from __future__ import annotations

import json

from fastapi import APIRouter, Request, Depends
from sse_starlette.sse import EventSourceResponse
from nexus.api.streaming import safe_stream
from nexus.core.agent_runtime import RunCancellationContext, active_run_registry
from nexus.core.schemas import ChatCancelRequest, ChatRequestContext
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
SSE_PING_INTERVAL_SECONDS = 10

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

    # 去除首尾空格。
    context.user_prompt = context.user_prompt.strip() if context.user_prompt else ""

    # Chat 模式需要模型配置与有效输入；
    # Builder / Debugger 当前为禁用入口，应直接返回占位响应，不再复用 Chat 的输入校验。
    if context.mode == "chat":
        if not context.model_config_id:
            raise ParmasValidationError("model_config_id is required")
        if not context.user_prompt and not context.execution_hints.has_items():
            raise ParmasValidationError("user_prompt is required")
    
    # 校验 session_id 是否存在
    if not context.session_id:
        raise ParmasValidationError("session_id is required")
    if not context.request_id:
        raise ParmasValidationError("request_id is required")

    token = set_log_session_id(context.session_id)
    try:
        logger.info(
            "[收到用户请求] agent=%s user_prompt=%s request_id=%s execution_hints=%s",
            context.mode,
            context.user_prompt,
            context.request_id,
            json.dumps(context.execution_hints.summary(), ensure_ascii=False, sort_keys=True),
        )
        cancellation_context = RunCancellationContext()

        # Chat Agent
        if context.mode == "chat":
            await active_run_registry.register(
                session_id=context.session_id,
                request_id=context.request_id,
                cancellation_context=cancellation_context,
            )
            return EventSourceResponse(
                safe_stream(
                    agent_service.handle_chat_request_with_cancellation(
                        context,
                        cancellation_context=cancellation_context,
                    ),
                    context.session_id,
                    request_id=context.request_id,
                    request=request,
                    cancellation_context=cancellation_context,
                ),
                headers=SSE_RESPONSE_HEADERS,
                ping=SSE_PING_INTERVAL_SECONDS,
            )

        # Builder Agent
        if context.mode == "builder":
            return EventSourceResponse(
                safe_stream(agent_service.handle_builder_request(context), context.session_id),
                headers=SSE_RESPONSE_HEADERS,
                ping=SSE_PING_INTERVAL_SECONDS,
            )

        # Debugger Agent
        return EventSourceResponse(
            safe_stream(agent_service.handle_debugger_request(context), context.session_id),
            headers=SSE_RESPONSE_HEADERS,
            ping=SSE_PING_INTERVAL_SECONDS,
        )
    finally:
        reset_log_session_id(token)


@router.post("/chat/cancel")
async def cancel_chat_completion(
    payload: ChatCancelRequest,
    request: Request,
):
    """显式取消单次 chat 流式请求。"""
    auth_token = request.headers.get("Authorization")
    if not auth_token:
        raise AuthError("Authorization token is required")
    if not check_login(auth_token):
        raise AuthError("Current user is not logged in")

    token = set_log_session_id(payload.session_id)
    try:
        logger.info(
            "[收到取消会话请求] session_id=%s request_id=%s",
            payload.session_id,
            payload.request_id,
        )
        cancel_result = await active_run_registry.cancel(
            session_id=payload.session_id,
            request_id=payload.request_id,
            reason="用户主动停止生成",
        )
        logger.info(
            "[取消会话完成] session_id=%s request_id=%s status=%s accepted=%s",
            payload.session_id,
            payload.request_id,
            cancel_result.status,
            cancel_result.accepted,
        )
        return {
            "code": 200,
            "data": {
                "status": cancel_result.status,
                "accepted": cancel_result.accepted,
                "cancelled": cancel_result.accepted,
            },
            "message": "success",
        }
    finally:
        reset_log_session_id(token)
