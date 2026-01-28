from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from typing import Dict
from config.logger import get_logger

logger = get_logger(__name__)

# 全局内存存储，用于保存会话历史
# 在生产环境中，应该使用 Redis 或数据库
store: Dict[str, BaseChatMessageHistory] = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    获取指定会话的历史记录。
    如果不存在，则创建一个新的历史记录。
    """
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]
