from typing import List, Optional
from cachetools import TTLCache
from nexus.core.schemas import NodeDefinition
from nexus.services.workflow_node_service import fetch_node_definitions
from nexus.config.logger import get_logger

logger = get_logger(__name__)

# 节点定义缓存，5 分钟刷新一次（全局仅缓存一份）
_NODE_CACHE = TTLCache(maxsize=1, ttl=300)
_NODE_CACHE_KEY = "nodes"


def _get_cached_nodes(auth_token: Optional[str] = None) -> List[NodeDefinition]:
    """
    获取节点定义缓存。如果缓存为空则请求接口并缓存。
    """
    cached = _NODE_CACHE.get(_NODE_CACHE_KEY)
    if cached is not None:
        return cached

    nodes = fetch_node_definitions(auth_token)
    if nodes:
        _NODE_CACHE[_NODE_CACHE_KEY] = nodes
        return nodes

    return []


class NodeRegistry:
    """
    管理 Agent 可用的节点集合。
    仅提供 get_all_nodes，直接读取缓存。
    """
    def get_all_nodes(self, auth_token: Optional[str] = None) -> List[NodeDefinition]:
        return _get_cached_nodes(auth_token)


# 全局单例实例
registry = NodeRegistry()
