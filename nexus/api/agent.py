from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from core.schemas import BuilderContext
from services.agent_service import AgentService
from container.dependencies import get_agent_service
from config.logger import get_logger
from services.auth_service import check_login
from common.exceptions import ParmasValidationError, AuthError

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/chat/completions")
async def chat_completions(
    context: BuilderContext, 
    request: Request,
    agent_service: AgentService = Depends(get_agent_service)
):
    """
    统一的智能体对话接口 
    支持流式响应
    根据 context.agent_type ("chat" | "builder") 分流处理不同智能体类型的请求。
    """
    context.auth_token = request.headers.get("Authorization")
    # 登录校验
    if not context.auth_token:
        raise AuthError("Authorization token is required")
    if not check_login(context.auth_token):
        raise AuthError("Current user is not logged in")

    # 校验 agent_type 是否有效
    if context.agent_type not in ["chat", "builder"]:
        logger.error(f"Invalid agent_type: {context.agent_type}")
        raise ParmasValidationError(f"Invalid agent type: {context.agent_type}")

    # 校验 model_config_id 是否存在
    if not context.model_config_id:
        raise ParmasValidationError("model_config_id is required")
    
    # 去除首尾空格并校验 user_prompt 非空
    context.user_prompt = context.user_prompt.strip() if context.user_prompt else ""
    if not context.user_prompt:
        raise ParmasValidationError("user_prompt is required")
    
    # 校验 current_graph 是否存在
    if not context.current_graph:
        raise ParmasValidationError("current_graph is required")
    
    # 校验 session_id 是否存在
    if not context.session_id:
        raise ParmasValidationError("session_id is required")

    logger.info(
        f"Received {context.agent_type} agent request with model_config_id: {context.model_config_id}, user_prompt: {context.user_prompt}")

    # Chat Agent
    if context.agent_type == "chat":
        return StreamingResponse(
            agent_service.handle_chat_request(context),
            media_type="text/event-stream"
        )

    # Builder Agent
    return StreamingResponse(
        agent_service.handle_builder_request(context),
        media_type="text/event-stream"
    )
