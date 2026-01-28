import json
from typing import Any, Dict, List, Tuple, Type

from langchain_core.tools import tool
from pydantic import BaseModel

from nexus.config.logger import get_logger
from nexus.core.schemas import BuilderContext, NodeDefinition, Operation

logger = get_logger(__name__)


class AgentTools:
    def __init__(self, context: BuilderContext, available_nodes: List[NodeDefinition]):
        self.context = context
        self.available_nodes = available_nodes

    def get_node_catalog(self) -> str:
        """
        获取可用节点的目录，包含节点类型、名称、输入输出参数的摘要。

        返回:
            包含节点目录的字符串，每个节点占一行
        """
        logger.info("Agent tool [get_node_catalog] - start. session_id=%s", self.context.session_id)
        def summarize_io(items: List[Dict[str, Any]]) -> List[str]:
            summary = []
            for item in items:
                key = item.get("key") or item.get("name")
                label = item.get("label")
                if key and label and key != label:
                    summary.append(f"{key}({label})")
                else:
                    summary.append(key or label or "unknown")
            return summary
        lines = []
        for node in self.available_nodes:
            inputs_summary = summarize_io(node.inputs)
            outputs_summary = summarize_io(node.outputs)
            lines.append(
                f"- type: {node.flow_node_type}, name: {node.name}, "
                f"inputs: {inputs_summary}, outputs: {outputs_summary}"
            )
        logger.info("Agent tool [get_node_catalog] - done. result_count=%d session_id=%s", len(lines), self.context.session_id)
        return "\n".join(lines)

    def get_current_graph(self) -> str:
        """
        获取当前图的节点与连线结构的摘要。

        返回:
            包含节点与连线结构的 JSON 字符串
        """
        logger.info("Agent tool [get_current_graph] - start. session_id=%s", self.context.session_id)
        if not self.context.current_graph:
            return json.dumps({"nodes": [], "edges": [], "chatConfig": []})

        g = self.context.current_graph
        nodes_simple = []
        for n in g.nodes:
            cfg = n.data if isinstance(n.data, dict) else {}
            nodes_simple.append({
                "id": cfg.get("nodeId") or n.id,
                "type": cfg.get("flowNodeType") or n.type,
                "name": cfg.get("name"),
                "intro": cfg.get("intro"),
                "inputs": cfg.get("inputs"),
                "outputs": cfg.get("outputs"),
            })

        edges_simple = [
            {"source": e.source, "target": e.target}
            for e in g.edges
        ]
        logger.info("Agent tool [get_current_graph] - done. nodes=%s edges=%s session_id=%s", nodes_simple, edges_simple, self.context.session_id)
        return json.dumps({"nodes": nodes_simple, "edges": edges_simple}, ensure_ascii=False)


def build_agent_tools(
    context: BuilderContext,
    available_nodes: List[NodeDefinition],
    submit_plan_schema: Type[BaseModel],
) -> Tuple[List, AgentTools]:
    """
    构建智能体工具函数。

    参数:
        context: 构建上下文，包含会话ID等信息
        available_nodes: 可用的节点定义列表
        submit_plan_schema: 提交计划的 Pydantic 模型

    返回:
        包含工具函数和工具实现的元组
    """
    tool_impl = AgentTools(context, available_nodes)

    @tool
    def get_node_catalog():
        """获取可用节点类型及其输入输出概要。"""
        return tool_impl.get_node_catalog()

    @tool
    def get_current_graph():
        """获取当前图的节点与连线结构。"""
        return tool_impl.get_current_graph()

    @tool(args_schema=submit_plan_schema)
    def submit_plan(thought: str, operations: List[Operation]):
        """提交构建操作计划。"""
        return "Plan submitted."

    tools = [get_node_catalog, get_current_graph, submit_plan]
    return tools, tool_impl
