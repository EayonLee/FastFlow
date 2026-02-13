import json
from threading import RLock
from typing import Any, Dict, List, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)


# 大结果日志统一走 debug，避免 info 被超长 JSON 淹没。
def _log_tool_result_debug(tool_name: str, session_id: str | None, result_json: str) -> None:
    logger.debug("Agent tool [%s] - tool result. session_id=%s result=%s", tool_name, session_id, result_json)


# 工作流图字段裁剪策略（按 workflow graph JSON 结构组织）。
WORKFLOW_GRAPH_PRUNE_RULES: Dict[str, Any] = {
    "nodes": {
        "drop_fields": ["avatar", "isFolded", "position", "version", "showStatus", "showResponse"],
        "inputs": {
            "drop_fields": ["renderTypeList", "llmModelType", "valueDesc", "debugLabel", "toolDescription", "editField",
                            "customInputConfig"]
        },
        "outputs": {"drop_fields": ["description", "type", "customFieldConfig"]},
    },
    "edges": {"drop_fields": ["zIndex", "type"]},
    "chatConfig": {
        "drop_fields": ["scheduledTriggerConfig"],
        "variables": {
            "drop_fields": ["icon", "list", "enums"]
        }
    }
}

# key: session_id, value: 最近一次上报的完整工作流图（dict）
# 说明：这是进程内缓存，用于“本次请求没带图时”的兜底读取。
WORKFLOW_GRAPH_CACHE: Dict[str, Dict[str, Any]] = {}
# 读写缓存需要加锁，避免并发请求出现竞争条件。
WORKFLOW_GRAPH_CACHE_LOCK = RLock()


class WorkflowGraphTools:
    """
    工作流图工具：
    1) 查询完整工作流图
    2) 查询单个节点详情
    3) 按关键词检索节点

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
        if not session_id or workflow_graph_data is None:
            return

        if hasattr(workflow_graph_data, "model_dump"):
            workflow_graph_dict = workflow_graph_data.model_dump(by_alias=True)
        elif isinstance(workflow_graph_data, dict):
            workflow_graph_dict = workflow_graph_data
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
        if workflow_graph_data is not None:
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

    def _prune_io_items(self, items: Any, drop_fields: List[str]) -> List[Dict[str, Any]]:
        """
        对输入/输出字段列表做统一裁剪。
        """
        if not isinstance(items, list):
            return []
        drop_fields_set = set(drop_fields)
        pruned_items: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            pruned_items.append({key: value for key, value in item.items() if key not in drop_fields_set})
        return pruned_items

    def _get_full_show_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        工作流图工具：获取“展示用完整图”。

        说明：
        - 数据源仍然是 _get_full_workflow_graph_dict（原始全量图）
        - 在此基础上按 nodes/edges 裁剪策略删除不必要字段
        """
        full_workflow_graph = self._get_full_workflow_graph_dict()
        node_drop_fields = set(WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["drop_fields"])
        node_input_drop_fields = WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["inputs"]["drop_fields"]
        node_output_drop_fields = WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["outputs"]["drop_fields"]
        edge_drop_fields = set(WORKFLOW_GRAPH_PRUNE_RULES["edges"]["drop_fields"])

        # 裁剪 nodes。
        pruned_nodes: List[Dict[str, Any]] = []
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue

            # 1) 先裁掉 nodes 顶层字段。
            pruned_node = {key: value for key, value in node.items() if key not in node_drop_fields}

            # 2) 裁剪顶层 inputs / outputs。
            top_inputs = pruned_node.get("inputs")
            top_outputs = pruned_node.get("outputs")
            if isinstance(top_inputs, list):
                pruned_node["inputs"] = self._prune_io_items(top_inputs, node_input_drop_fields)
            if isinstance(top_outputs, list):
                pruned_node["outputs"] = self._prune_io_items(top_outputs, node_output_drop_fields)

            pruned_nodes.append(pruned_node)

        # 裁剪 edges。
        pruned_edges: List[Dict[str, Any]] = []
        for edge in full_workflow_graph.get("edges", []):
            if not isinstance(edge, dict):
                continue
            pruned_edges.append({key: value for key, value in edge.items() if key not in edge_drop_fields})

        return {
            "nodes": pruned_nodes,
            "edges": pruned_edges,
            "chatConfig": full_workflow_graph.get("chatConfig", {}),
        }

    def get_full_workflow_graph(self) -> str:
        """
        工作流图工具：返回完整工作流图 JSON。
        """
        logger.info("Agent tool [get_full_workflow_graph] - start. session_id=%s", self.context.session_id)
        full_workflow_graph = self._get_full_show_workflow_graph_dict()
        result_json = json.dumps(full_workflow_graph, ensure_ascii=False)
        logger.info(
            "Agent tool [get_full_workflow_graph] - done. node_count=%d edge_count=%d session_id=%s",
            len(full_workflow_graph.get("nodes", [])),
            len(full_workflow_graph.get("edges", [])),
            self.context.session_id,
        )
        _log_tool_result_debug("get_full_workflow_graph", self.context.session_id, result_json)
        return result_json

    def get_workflow_node_info(self, node_id: str) -> str:
        """
        工作流图工具：按节点 ID 查询节点详情。

        返回结构与节点检索接口一致，便于前端统一渲染。
        """
        logger.info(
            "Agent tool [get_workflow_node_info] - start. node_id=%s session_id=%s",
            node_id,
            self.context.session_id,
        )
        full_workflow_graph = self._get_full_show_workflow_graph_dict()
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            workflow_graph_node = {
                "id": node.get("nodeId"),
                "type": node.get("flowNodeType"),
                "name": node.get("name"),
                "intro": node.get("intro"),
                "inputs": node.get("inputs"),
                "outputs": node.get("outputs"),
            }
            # 命中目标节点后立即返回，避免无效遍历。
            if workflow_graph_node.get("id") == node_id:
                result_json = json.dumps(workflow_graph_node, ensure_ascii=False)
                logger.info(
                    "Agent tool [get_workflow_node_info] - done. found=true node_type=%s session_id=%s",
                    workflow_graph_node.get("type"),
                    self.context.session_id,
                )
                _log_tool_result_debug("get_workflow_node_info", self.context.session_id, result_json)
                return result_json
        # 未命中时返回统一错误结构。
        error_result = {"error": f"node not found: {node_id}"}
        error_result_json = json.dumps(error_result, ensure_ascii=False)
        logger.info(
            "Agent tool [get_workflow_node_info] - done. found=false node_id=%s session_id=%s",
            node_id,
            self.context.session_id,
        )
        _log_tool_result_debug("get_workflow_node_info", self.context.session_id, error_result_json)
        return error_result_json

    def find_workflow_graph_nodes(self, query: str) -> str:
        """
        工作流图工具：按关键词检索节点（name/type/intro）。

        说明：检索不区分大小写；仅对 name/type/intro 三个字段做包含匹配。
        """
        # 统一清洗输入，避免空格和大小写影响匹配结果。
        query_text = (query or "").strip().lower()
        logger.info(
            "Agent tool [find_workflow_graph_nodes] - start. query=%s session_id=%s",
            query_text,
            self.context.session_id,
        )
        if not query_text:
            empty_result_json = json.dumps([], ensure_ascii=False)
            logger.info(
                "Agent tool [find_workflow_graph_nodes] - done. matched=0(empty_query) session_id=%s",
                self.context.session_id,
            )
            return empty_result_json

        full_workflow_graph = self._get_full_show_workflow_graph_dict()
        matched_nodes = []
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            # 按统一字段构造节点检索文本：nodeId / name / intro / flowNodeType
            workflow_graph_node_id = node.get("nodeId")
            workflow_graph_node_type = node.get("flowNodeType")
            workflow_graph_node_name = node.get("name")
            workflow_graph_node_intro = node.get("intro")

            search_chunks = [
                str(workflow_graph_node_id or ""),
                str(workflow_graph_node_name or ""),
                str(workflow_graph_node_intro or ""),
                str(workflow_graph_node_type or ""),
            ]
            searchable_text = " ".join(search_chunks).lower()

            if query_text in searchable_text:
                # 仅在命中时构造返回节点对象，减少无效对象创建。
                matched_nodes.append(
                    {
                        "id": workflow_graph_node_id,
                        "type": workflow_graph_node_type,
                        "name": workflow_graph_node_name,
                        "intro": workflow_graph_node_intro,
                    }
                )
        result_json = json.dumps(matched_nodes, ensure_ascii=False)
        logger.info(
            "Agent tool [find_workflow_graph_nodes] - done. matched=%d session_id=%s",
            len(matched_nodes),
            self.context.session_id,
        )
        _log_tool_result_debug("find_workflow_graph_nodes", self.context.session_id, result_json)
        return result_json


def build_workflow_graph_tools(context: ChatRequestContext) -> Tuple[List, WorkflowGraphTools]:
    """
    工作流图工具：构建工具列表（Chat/Builder 都可复用）。

    返回：
    - tools: 提供给 LangChain 的可调用工具列表
    - tool_impl: 具体实现对象（便于外层在需要时直接调用）
    """
    tool_impl = WorkflowGraphTools(context)

    @tool
    def get_full_workflow_graph():
        """工作流图工具：获取当前工作流图完整结构，包含：节点完整信息、节点连线拓扑关系、全局配置。"""
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
        get_full_workflow_graph,
        get_workflow_node_info,
        find_workflow_graph_nodes,
    ], tool_impl
