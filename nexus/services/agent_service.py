import json
from typing import AsyncGenerator, Dict

from nexus.agents.chat import ChatAgent
from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)
SSE_DONE = "data: [DONE]\n\n"


def _to_sse(payload: Dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class AgentService:
    """
    智能体服务层
    """

    def __init__(self, chat_agent: ChatAgent):
        self.chat_agent = chat_agent

    async def handle_chat_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """处理对话型智能体请求。"""
        try:
            async for chunk in self.chat_agent.achat(context):
                yield _to_sse({"type": "chunk", "content": chunk})
        except BusinessError as e:
            logger.error("ChatAgent error: %s", e)
            yield _to_sse({"type": "error", "message": e.message})
        except Exception as e:
            logger.error("ChatAgent error. user_prompt=%s error=%s", context.user_prompt, e)
            yield _to_sse({"type": "error", "message": str(e)})

        yield SSE_DONE

    async def handle_builder_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理构建型智能体请求（保留入口，内部逻辑已清空）。
        """
        logger.info("BuilderAgent is disabled.")
        yield _to_sse({"type": "error", "message": "Builder agent is temporarily disabled"})
        yield SSE_DONE
