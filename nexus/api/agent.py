import json
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from nexus.core.schemas import ChatRequestContext
from nexus.services.agent_service import AgentService
from nexus.common.dependencies import get_agent_service
from nexus.config.logger import get_logger
from nexus.services.auth_service import check_login
from nexus.common.exceptions import ParmasValidationError, AuthError

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


async def _safe_stream(stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """包装流式输出，确保异常被记录并转换为 SSE 错误事件。"""
    try:
        async for chunk in stream:
            yield chunk
    except Exception as exc:
        logger.exception("Streaming response error")
        payload = {"type": "error", "message": f"Streaming error: {str(exc)}"}
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

@router.post("/chat/completions")
async def chat_completions(
    context: ChatRequestContext,
    request: Request,
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    统一的智能体对话接口 
    支持流式响应
    根据 context.mode ("chat" | "builder") 分流处理不同智能体类型的请求。
    """
    context.auth_token = request.headers.get("Authorization")
    # 登录校验
    if not context.auth_token:
        raise AuthError("Authorization token is required")
    if not check_login(context.auth_token):
        raise AuthError("Current user is not logged in")

    # 校验 mode 是否有效
    if context.mode not in ["chat", "builder"]:
        logger.error("Invalid agent mode: %s", context.mode)
        raise ParmasValidationError(f"Invalid agent mode: {context.mode}")

    # 校验 model_config_id 是否存在
    if not context.model_config_id:
        raise ParmasValidationError("model_config_id is required")
    
    # 去除首尾空格并校验 user_prompt 非空
    context.user_prompt = context.user_prompt.strip() if context.user_prompt else ""
    if not context.user_prompt:
        raise ParmasValidationError("user_prompt is required")
    
    # 校验 session_id 是否存在
    if not context.session_id:
        raise ParmasValidationError("session_id is required")

    logger.info(
        f"Received {context.mode} agent request with model_config_id: {context.model_config_id}, user_prompt: {context.user_prompt}")

    # Chat Agent
    if context.mode == "chat":
        return StreamingResponse(
            _safe_stream(agent_service.handle_chat_request(context)),
            media_type="text/event-stream"
        )

    # Builder Agent
    return StreamingResponse(
        _safe_stream(agent_service.handle_builder_request(context)),
        media_type="text/event-stream"
    )
