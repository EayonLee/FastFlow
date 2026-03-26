from langchain_core.chat_history import BaseChatMessageHistory
from nexus.core.cache import CacheManager


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    获取指定会话的历史记录。

    说明：
    - 返回的是“可变历史对象”本身，而不是副本；
    - 调用方直接对该对象执行 `add_messages` 即可完成整轮保存；
    - 因此这里不需要额外 `set_session_history` 方法。
    """
    return CacheManager.get_session_history(str(session_id or "").strip())
