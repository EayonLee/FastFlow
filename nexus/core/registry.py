from typing import Dict, List, Optional
from core.schemas import NodeDefinition
from services.workflow_node_service import fetch_node_definitions
from config.logger import get_logger

logger = get_logger(__name__)

class NodeRegistry:
    """
    管理 Agent 可用的节点集合。
    """
    def __init__(self):
        self._registry: Dict[str, NodeDefinition] = {}

    def refresh_nodes(self, auth_token: Optional[str] = None):
        """
        刷新节点定义。
        """
        try:
            nodes = fetch_node_definitions(auth_token)
            if nodes:
                # 清空旧数据或增量更新，这里选择直接覆盖以保证一致性
                self._registry.clear()
                for node in nodes:
                    self.register(node)
                # 总是保留必须的系统节点（如果没返回的话）
                self._ensure_system_nodes()
        except Exception as e:
            logger.error(f"Failed to refresh nodes: {e}")

    def _ensure_system_nodes(self):
        """
        确保基础系统节点存在。
        """
        if "workflow-start" not in self._registry:
            self.register(NodeDefinition(
                type="workflow-start",
                label="开始节点",
                category="逻辑",
                output_type="Any"
            ))

    def register(self, node_def: NodeDefinition):
        """
        注册新的节点类型。
        """
        self._registry[node_def.type] = node_def

    def get_node(self, node_type: str) -> Optional[NodeDefinition]:
        """
        通过类型检索节点定义。
        """
        return self._registry.get(node_type)

    def get_all_nodes(self) -> List[NodeDefinition]:
        """
        获取所有注册的节点。
        """
        # 如果注册表为空，尝试初始化（虽然在 Agent 请求时应该已经有 Token 触发刷新，但做个兜底）
        # 注意：这里没有 Token，只能获取公共节点或报错，或者依赖外部显式调用 refresh
        if not self._registry:
            self._ensure_system_nodes()
            
        return list(self._registry.values())

    def to_prompt_format(self) -> str:
        """
        将注册表序列化为适合 LLM 系统提示的格式。
        """
        lines = ["可用节点:"]
        for node in self._registry.values():
            # TODO: 丰富此处内容，加入输入/输出/schema 以便 LLM 更好地理解
            lines.append(f"- {node.type}: {node.label} (分类: {node.category})")
        return "\n".join(lines)

# 全局单例实例
registry = NodeRegistry()

# 初始化时只加载系统节点，实际业务节点应在请求上下文（带Token）中动态加载
registry._ensure_system_nodes()

