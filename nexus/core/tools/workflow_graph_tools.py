import json
from collections import Counter
from threading import RLock
from typing import Any, Dict, List, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)

# key: session_id, value: 最近一次上报的完整工作流图（dict）
# 说明：这是进程内缓存，用于“本次请求没带图时”的兜底读取。
WORKFLOW_GRAPH_CACHE: Dict[str, Dict[str, Any]] = {}
# 读写缓存需要加锁，避免并发请求出现竞争条件。
WORKFLOW_GRAPH_CACHE_LOCK = RLock()


class WorkflowGraphTools:
    """
    工作流图工具：
    1) 查询完整工作流图
    2) 查询工作流图摘要
    3) 查询单个节点详情
    4) 按关键词检索节点

    调用链路：
    - 外层通过 build_workflow_graph_tools 注册 LangChain tool
    - tool 调用本类公开方法
    - 公开方法统一通过 _get_full_workflow_graph_dict 取图数据
    """

    def __init__(self, context: ChatRequestContext):
        # 当前请求上下文，包含 session_id / workflow_graph 等字段。
        self.context = context
        # 初始化时尝试把本次请求图写入缓存，便于后续请求复用。
        self._cache_workflow_graph()

    def _cache_workflow_graph(self) -> None:
        """
        工作流图工具：将当前请求中的完整工作流图写入会话缓存。

        仅在满足以下条件时写入：
        - session_id 存在
        - workflow_graph 存在，且可转为 dict
        """
        session_id = self.context.session_id
        workflow_graph_data = self.context.workflow_graph
        # 没有会话或没有图，不缓存。
        if not session_id or not workflow_graph_data:
            return

        # pydantic 模型优先用 model_dump，确保 alias 字段生效。
        if hasattr(workflow_graph_data, "model_dump"):
            workflow_graph_dict = workflow_graph_data.model_dump(by_alias=True)
        # 已经是 dict 时直接使用。
        elif isinstance(workflow_graph_data, dict):
            workflow_graph_dict = workflow_graph_data
        # 其他类型不处理，直接返回。
        else:
            return

        with WORKFLOW_GRAPH_CACHE_LOCK:
            WORKFLOW_GRAPH_CACHE[session_id] = workflow_graph_dict

    def _get_full_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        工作流图工具：获取完整工作流图。

        优先级：
        1) 优先当前请求
        2) 否则会话缓存
        3) 最后空图
        """
        workflow_graph_data = self.context.workflow_graph
        if workflow_graph_data:
            if hasattr(workflow_graph_data, "model_dump"):
                return workflow_graph_data.model_dump(by_alias=True)
            if isinstance(workflow_graph_data, dict):
                return workflow_graph_data

        session_id = self.context.session_id
        # 当前请求没带图时，按 session_id 到缓存读取最近一次图。
        if session_id:
            with WORKFLOW_GRAPH_CACHE_LOCK:
                cached_workflow_graph = WORKFLOW_GRAPH_CACHE.get(session_id)
            if cached_workflow_graph:
                return cached_workflow_graph

        # 兜底空结构，保证后续逻辑无需判空。
        return {"nodes": [], "edges": [], "chatConfig": {}}

    def get_full_workflow_graph(self) -> str:
        """
        工作流图工具：返回完整工作流图 JSON。
        """
        logger.info("Agent tool [get_workflow_graph] - start. session_id=%s", self.context.session_id)
        full_workflow_graph = self._get_full_workflow_graph_dict()
        logger.info(
            "Agent tool [get_workflow_graph] - done. node_count=%d edge_count=%d session_id=%s",
            len(full_workflow_graph.get("nodes", [])),
            len(full_workflow_graph.get("edges", [])),
            self.context.session_id,
        )
        return json.dumps(full_workflow_graph, ensure_ascii=False)

    def get_workflow_graph_summary(self) -> str:
        """
        工作流图工具：返回工作流图摘要（节点数、边数、类型分布）。
        """
        logger.info("Agent tool [get_workflow_graph_summary] - start. session_id=%s", self.context.session_id)

        full_workflow_graph = self._get_full_workflow_graph_dict()
        # 节点统计：节点总数 + 节点类型分布。
        node_count = 0
        type_counter = Counter()
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_count += 1
            node_data = node.get("data")
            if not isinstance(node_data, dict):
                node_data = {}
            workflow_graph_node_type = (
                node_data.get("flowNodeType") or node.get("flowNodeType") or node.get("type") or "unknown"
            )
            type_counter[workflow_graph_node_type] += 1

        # 边统计：仅统计合法 dict 结构的边。
        edge_count = sum(1 for edge in full_workflow_graph.get("edges", []) if isinstance(edge, dict))
        summary = {
            "node_count": node_count,
            "edge_count": edge_count,
            "node_type_distribution": dict(type_counter),
        }
        logger.info(
            "Agent tool [get_workflow_graph_summary] - done. summary=%s session_id=%s",
            summary,
            self.context.session_id,
        )
        return json.dumps(summary, ensure_ascii=False)

    def get_workflow_node_info(self, node_id: str) -> str:
        """
        工作流图工具：按节点 ID 查询节点详情。

        返回结构与节点检索接口一致，便于前端统一渲染。
        """
        full_workflow_graph = self._get_full_workflow_graph_dict()
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_data = node.get("data")
            if not isinstance(node_data, dict):
                node_data = {}
            workflow_graph_node = {
                "id": node_data.get("nodeId") or node.get("nodeId") or node.get("id"),
                "type": node_data.get("flowNodeType") or node.get("flowNodeType") or node.get("type"),
                "name": node_data.get("name"),
                "intro": node_data.get("intro"),
                    "inputs": node_data.get("inputs"),
                    "outputs": node_data.get("outputs"),
                }
            # 命中目标节点后立即返回，避免无效遍历。
            if workflow_graph_node.get("id") == node_id:
                return json.dumps(workflow_graph_node, ensure_ascii=False)
        # 未命中时返回统一错误结构。
        return json.dumps({"error": f"node not found: {node_id}"}, ensure_ascii=False)

    def find_workflow_graph_nodes(self, query: str) -> str:
        """
        工作流图工具：按关键词检索节点（name/type/intro）。

        说明：检索不区分大小写；仅对 name/type/intro 三个字段做包含匹配。
        """
        # 统一清洗输入，避免空格和大小写影响匹配结果。
        query_text = (query or "").strip().lower()
        if not query_text:
            return json.dumps([], ensure_ascii=False)

        full_workflow_graph = self._get_full_workflow_graph_dict()
        matched_nodes = []
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_data = node.get("data")
            if not isinstance(node_data, dict):
                node_data = {}

            workflow_graph_node_type = node_data.get("flowNodeType") or node.get("flowNodeType") or node.get("type")
            workflow_graph_node_name = node_data.get("name")
            workflow_graph_node_intro = node_data.get("intro")

            name = (workflow_graph_node_name or "").lower()
            node_type = (workflow_graph_node_type or "").lower()
            intro = (workflow_graph_node_intro or "").lower()
            if query_text in name or query_text in node_type or query_text in intro:
                # 仅在命中时构造返回节点对象，减少无效对象创建。
                matched_nodes.append(
                    {
                        "id": node_data.get("nodeId") or node.get("nodeId") or node.get("id"),
                        "type": workflow_graph_node_type,
                        "name": workflow_graph_node_name,
                        "intro": workflow_graph_node_intro,
                        "inputs": node_data.get("inputs"),
                        "outputs": node_data.get("outputs"),
                    }
                )
        return json.dumps(matched_nodes, ensure_ascii=False)


def build_workflow_graph_tools(context: ChatRequestContext) -> Tuple[List, WorkflowGraphTools]:
    """
    工作流图工具：构建工具列表（Chat/Builder 都可复用）。

    返回：
    - tools: 提供给 LangChain 的可调用工具列表
    - tool_impl: 具体实现对象（便于外层在需要时直接调用）
    """
    tool_impl = WorkflowGraphTools(context)

    @tool
    def get_workflow_graph_summary():
        """工作流图工具：获取当前工作流图摘要。"""
        return tool_impl.get_workflow_graph_summary()

    @tool
    def get_full_workflow_graph():
        """工作流图工具：获取当前工作流图完整结构。"""
        return tool_impl.get_full_workflow_graph()

    @tool
    def get_workflow_node_info(node_id: str):
        """工作流图工具：根据节点 ID 获取节点详情。"""
        return tool_impl.get_workflow_node_info(node_id)

    @tool
    def find_workflow_graph_nodes(query: str):
        """工作流图工具：按关键词检索节点。"""
        return tool_impl.find_workflow_graph_nodes(query)

    # 返回固定顺序，便于调试与观测。
    return [
        get_workflow_graph_summary,
        get_full_workflow_graph,
        get_workflow_node_info,
        find_workflow_graph_nodes,
    ], tool_impl
