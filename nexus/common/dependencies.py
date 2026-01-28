from functools import lru_cache
from nexus.agents.builder import BuilderAgent
from nexus.agents.chat import ChatAgent
from nexus.agents.helpers.layouter import Layouter
from nexus.services.agent_service import AgentService
from nexus.config.logger import get_logger

logger = get_logger(__name__)

@lru_cache()
def get_builder_agent() -> BuilderAgent:
    """
    获取 BuilderAgent 的单例实例。
    使用 lru_cache 确保整个应用生命周期内只创建一个 Agent 实例，
    以便复用内部的 Runnable 缓存和连接池。
    """
    return BuilderAgent()

@lru_cache()
def get_chat_agent() -> ChatAgent:
    """
    获取 ChatAgent 的单例实例。
    """
    return ChatAgent()

@lru_cache()
def get_layouter() -> Layouter:
    """
    获取 Layouter 的单例实例。
    """
    return Layouter()

@lru_cache()
def get_agent_service() -> AgentService:
    """
    获取 AgentService 的单例实例。
    """
    return AgentService(
        builder_agent=get_builder_agent(),
        chat_agent=get_chat_agent(),
        layouter=get_layouter()
    )
