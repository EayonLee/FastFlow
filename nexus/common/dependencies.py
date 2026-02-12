from functools import lru_cache

from nexus.agents.chat import ChatAgent
from nexus.services.agent_service import AgentService


@lru_cache()
def get_chat_agent() -> ChatAgent:
    """
    获取 ChatAgent 的单例实例。
    """
    return ChatAgent()


@lru_cache()
def get_agent_service() -> AgentService:
    """
    获取 AgentService 的单例实例。
    """
    return AgentService(chat_agent=get_chat_agent())
