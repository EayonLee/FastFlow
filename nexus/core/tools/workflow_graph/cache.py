"""
工作流图缓存与统一读取入口。

为什么需要这个模块：
1. 前端会导出 workflow_graph JSON 并上报给 Nexus。
2. 同一会话的后续问题，前端可能不再重复携带 workflow_graph。
3. 我们用 session_id 做 key，在进程内做一次缓存兜底。

注意事项：
- 这是进程内缓存，不会跨进程/跨机器共享；不能当作强一致数据源。
- 仅用于“本次请求没带图”时的兜底读取，真实来源仍以请求体为准。
- 通过锁保证并发请求下读写安全。
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Dict, List

from nexus.core.schemas import ChatRequestContext
from nexus.config.logger import get_logger

logger = get_logger(__name__)

# 进程内缓存：session_id -> workflow_graph dict
_WORKFLOW_GRAPH_CACHE: Dict[str, Dict[str, Any]] = {}
_WORKFLOW_GRAPH_CACHE_LOCK = RLock()

# 工作流图字段裁剪策略（按 workflow graph JSON 结构组织）。
# 目的：
# - 降低 token（避免把 UI 细节喂给大模型）
# - 去除与推理无关的展示字段
WORKFLOW_GRAPH_PRUNE_RULES: Dict[str, Any] = {
    "nodes": {
        "drop_fields": ["avatar", "isFolded", "position", "version", "showStatus", "showResponse"],
        "inputs": {
            "drop_fields": [
                "renderTypeList",
                "llmModelType",
                "valueDesc",
                "debugLabel",
                "toolDescription",
                "editField",
                "customInputConfig",
            ]
        },
        "outputs": {"drop_fields": ["description", "type", "customFieldConfig"]},
    },
    "edges": {"drop_fields": ["zIndex", "type"]},
    "chatConfig": {
        "drop_fields": ["scheduledTriggerConfig"],
        "variables": {"drop_fields": ["icon", "list", "enums"]},
    },
}


def _cache_workflow_graph(session_id: str, workflow_graph_dict: Dict[str, Any]) -> None:
    """
    将 workflow_graph_dict 缓存到 session_id 下。

    说明：为避免缓存污染，这里只接受 dict 结构的图数据。
    """
    if not session_id:
        return
    if not isinstance(workflow_graph_dict, dict):
        return
    with _WORKFLOW_GRAPH_CACHE_LOCK:
        _WORKFLOW_GRAPH_CACHE[session_id] = workflow_graph_dict


def _get_cached_workflow_graph(session_id: str) -> Dict[str, Any] | None:
    """
    读取 session_id 对应的缓存 workflow_graph dict。

    未命中返回 None。
    """
    if not session_id:
        return None
    with _WORKFLOW_GRAPH_CACHE_LOCK:
        return _WORKFLOW_GRAPH_CACHE.get(session_id)


def _log_tool_result_debug(tool_name: str, session_id: str | None, result_json: str) -> None:
    """
    统一打印“工具最终返回值”的 debug 日志。

    说明：
    - 工具返回往往是较大的 JSON，info 打印会淹没正常日志，所以统一走 debug。
    """
    logger.debug("Agent tool [%s] - tool result. session_id=%s result=%s", tool_name, session_id, result_json)


def _prune_io_items(items: Any, drop_fields: List[str]) -> List[Dict[str, Any]]:
    """
    对 inputs/outputs 的字段数组做统一裁剪。
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


def prune_workflow_graph_for_show(full_workflow_graph: Dict[str, Any]) -> Dict[str, Any]:
    """
    将“原始全量图”裁剪为“展示用完整图”。

    说明：
    - 保留 nodes/edges/chatConfig 的结构与关键字段
    - 删除 UI-only 字段与不必要字段，减少上下文噪音
    """
    node_drop_fields = set(WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["drop_fields"])
    node_input_drop_fields = WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["inputs"]["drop_fields"]
    node_output_drop_fields = WORKFLOW_GRAPH_PRUNE_RULES["nodes"]["outputs"]["drop_fields"]
    edge_drop_fields = set(WORKFLOW_GRAPH_PRUNE_RULES["edges"]["drop_fields"])

    pruned_nodes: List[Dict[str, Any]] = []
    for node in full_workflow_graph.get("nodes", []):
        if not isinstance(node, dict):
            continue

        # 1) 先裁掉 nodes 顶层字段。
        pruned_node = {key: value for key, value in node.items() if key not in node_drop_fields}

        # 2) 裁剪 inputs / outputs（只删字段，不改结构）。
        top_inputs = pruned_node.get("inputs")
        top_outputs = pruned_node.get("outputs")
        if isinstance(top_inputs, list):
            pruned_node["inputs"] = _prune_io_items(top_inputs, node_input_drop_fields)
        if isinstance(top_outputs, list):
            pruned_node["outputs"] = _prune_io_items(top_outputs, node_output_drop_fields)

        pruned_nodes.append(pruned_node)

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


class WorkflowGraphCache:
    """
    workflow_graph 的统一读取入口 + session 级缓存（进程内）：
    - 优先读取当前请求 context.workflow_graph
    - 否则读取进程内 session cache
    - 兜底返回空图结构
    """

    def __init__(self, context: ChatRequestContext):
        # 保存当前请求上下文（session_id + workflow_graph）。
        self._context = context

    def cache_if_present(self) -> None:
        """
        如果当前请求携带 workflow_graph，则写入 session 缓存。

        这样后续请求可以不带 workflow_graph 仍可回答图相关问题（尽力兜底）。
        """
        session_id = self._context.session_id
        workflow_graph_data = self._context.workflow_graph
        if not session_id or workflow_graph_data is None:
            return

        # pydantic 模型用 model_dump 保留 alias 字段（如 chatConfig）。
        if hasattr(workflow_graph_data, "model_dump"):
            workflow_graph_dict = workflow_graph_data.model_dump(by_alias=True)
        elif isinstance(workflow_graph_data, dict):
            workflow_graph_dict = workflow_graph_data
        else:
            # 未知类型不缓存，避免污染缓存。
            return

        _cache_workflow_graph(session_id, workflow_graph_dict)

    def _get_full_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“全量工作流图 dict”（未裁剪）。

        优先级：
        1) context.workflow_graph（本次请求）
        2) session 进程内缓存
        3) 空图骨架
        """
        workflow_graph_data = self._context.workflow_graph
        if workflow_graph_data is not None:
            if hasattr(workflow_graph_data, "model_dump"):
                return workflow_graph_data.model_dump(by_alias=True)
            if isinstance(workflow_graph_data, dict):
                return workflow_graph_data

        session_id = self._context.session_id
        cached = _get_cached_workflow_graph(session_id) if session_id else None
        if cached:
            return cached

        # 兜底：返回稳定 key 的空结构，避免下游判空。
        return {"nodes": [], "edges": [], "chatConfig": {}}

    def get_full_show_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“展示用完整图”（已裁剪）。

        用途：
        - 给大模型/前端展示用，尽量减少无关字段与 token 噪音。
        """
        full_graph = self._get_full_workflow_graph_dict()
        return prune_workflow_graph_for_show(full_graph)


__all__ = [
    "WorkflowGraphCache",
    "_log_tool_result_debug",
    "prune_workflow_graph_for_show",
    "WORKFLOW_GRAPH_PRUNE_RULES",
]
