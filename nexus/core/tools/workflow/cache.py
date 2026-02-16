"""
工作流上下文缓存与统一读取入口。

为什么需要这个模块：
1. 前端会导出 workflow_graph JSON 并上报给 Nexus。
2. 前端也可携带 workflow_meta（工作流名称、描述）增强分析上下文。
3. 同一会话的后续问题，前端可能不再重复携带这些字段。
4. 我们用 session_id 做 key，在进程内做一次缓存兜底。

注意事项：
- 这是进程内缓存，不会跨进程/跨机器共享；不能当作强一致数据源。
- 仅用于“本次请求没带图/元信息”时的兜底读取，真实来源仍以请求体为准。
- 通过锁保证并发请求下读写安全。
"""

from __future__ import annotations

from threading import RLock
from typing import Any, Dict, List

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)

CACHE_KEY_WORKFLOW_GRAPH = "workflow_graph"
CACHE_KEY_WORKFLOW_META = "workflow_meta"

# 进程内会话上下文缓存：session_id -> {workflow_graph: {...}, workflow_meta: {...}}
# 兼容旧结构：历史缓存可能直接是 workflow_graph dict。
_SESSION_CONTEXT_CACHE: Dict[str, Dict[str, Any]] = {}
_SESSION_CONTEXT_CACHE_LOCK = RLock()

_EMPTY_WORKFLOW_META: Dict[str, str] = {"workflow_name": "", "workflow_description": ""}

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


def _build_empty_workflow_graph() -> Dict[str, Any]:
    """
    构造空工作流图骨架（返回全新对象，避免共享可变列表）。
    """
    return {"nodes": [], "edges": [], "chatConfig": {}}


def _normalize_workflow_meta(workflow_meta: Dict[str, Any] | None) -> Dict[str, str]:
    """
    归一化 workflow_meta，只保留两个稳定键并确保值为字符串。
    """
    if not isinstance(workflow_meta, dict):
        return dict(_EMPTY_WORKFLOW_META)

    workflow_name = workflow_meta.get("workflow_name")
    workflow_description = workflow_meta.get("workflow_description")
    return {
        "workflow_name": workflow_name if isinstance(workflow_name, str) else "",
        "workflow_description": workflow_description if isinstance(workflow_description, str) else "",
    }


def _normalize_session_context_entry(entry: Dict[str, Any] | None) -> Dict[str, Any]:
    """
    归一化 session 缓存结构：
    - 新结构：{workflow_graph: {...}, workflow_meta: {...}}
    - 旧结构：直接 workflow_graph dict
    """
    if not isinstance(entry, dict):
        return {}

    has_new_shape = CACHE_KEY_WORKFLOW_GRAPH in entry or CACHE_KEY_WORKFLOW_META in entry
    if has_new_shape:
        normalized: Dict[str, Any] = {}
        workflow_graph = entry.get(CACHE_KEY_WORKFLOW_GRAPH)
        workflow_meta = entry.get(CACHE_KEY_WORKFLOW_META)
        if isinstance(workflow_graph, dict):
            normalized[CACHE_KEY_WORKFLOW_GRAPH] = workflow_graph
        if isinstance(workflow_meta, dict):
            normalized[CACHE_KEY_WORKFLOW_META] = _normalize_workflow_meta(workflow_meta)
        return normalized

    # 兼容旧结构：entry 本身就是 workflow_graph dict。
    return {CACHE_KEY_WORKFLOW_GRAPH: entry}


def _get_cached_session_context(session_id: str) -> Dict[str, Any] | None:
    """
    读取 session 缓存并做结构归一化。
    """
    if not session_id:
        return None

    with _SESSION_CONTEXT_CACHE_LOCK:
        raw_entry = _SESSION_CONTEXT_CACHE.get(session_id)

    normalized = _normalize_session_context_entry(raw_entry) if isinstance(raw_entry, dict) else {}
    return normalized if normalized else None


def _merge_session_context(
    session_id: str,
    workflow_graph_dict: Dict[str, Any] | None = None,
    workflow_meta_dict: Dict[str, Any] | None = None,
) -> None:
    """
    将 workflow_graph / workflow_meta 合并写入同一 session 缓存。
    """
    if not session_id:
        return

    next_workflow_graph = workflow_graph_dict if isinstance(workflow_graph_dict, dict) else None
    next_workflow_meta = _normalize_workflow_meta(workflow_meta_dict) if isinstance(workflow_meta_dict, dict) else None
    if next_workflow_graph is None and next_workflow_meta is None:
        return

    with _SESSION_CONTEXT_CACHE_LOCK:
        current = _normalize_session_context_entry(_SESSION_CONTEXT_CACHE.get(session_id))
        if next_workflow_graph is not None:
            current[CACHE_KEY_WORKFLOW_GRAPH] = next_workflow_graph
        if next_workflow_meta is not None:
            current[CACHE_KEY_WORKFLOW_META] = next_workflow_meta
        _SESSION_CONTEXT_CACHE[session_id] = current


def _get_cached_workflow_graph(session_id: str) -> Dict[str, Any] | None:
    """
    读取 session_id 对应的缓存 workflow_graph。
    """
    cached_context = _get_cached_session_context(session_id)
    if not cached_context:
        return None

    workflow_graph = cached_context.get(CACHE_KEY_WORKFLOW_GRAPH)
    return workflow_graph if isinstance(workflow_graph, dict) else None


def _get_cached_workflow_meta(session_id: str) -> Dict[str, str] | None:
    """
    读取 session_id 对应的缓存 workflow_meta。
    """
    cached_context = _get_cached_session_context(session_id)
    if not cached_context:
        return None

    workflow_meta = cached_context.get(CACHE_KEY_WORKFLOW_META)
    if not isinstance(workflow_meta, dict):
        return None
    return _normalize_workflow_meta(workflow_meta)


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
    workflow_graph / workflow_meta 的统一读取入口 + session 级缓存（进程内）：
    - 优先读取当前请求 context.workflow_graph
    - 优先读取当前请求 context.workflow_meta
    - 否则读取进程内 session cache
    - 兜底返回空结构
    """

    def __init__(self, context: ChatRequestContext):
        # 保存当前请求上下文（session_id + workflow_graph + workflow_meta）。
        self._context = context

    def cache_if_present(self) -> None:
        """
        如果当前请求携带 workflow_graph / workflow_meta，则写入 session 缓存。

        这样后续请求可以不带这些字段仍可尽力兜底。
        """
        session_id = self._context.session_id
        if not session_id:
            return

        workflow_graph_dict = self._to_workflow_graph_dict(self._context.workflow_graph)
        workflow_meta_dict = self._to_workflow_meta_dict(self._context.workflow_meta)
        if workflow_graph_dict is None and workflow_meta_dict is None:
            return

        _merge_session_context(session_id, workflow_graph_dict=workflow_graph_dict, workflow_meta_dict=workflow_meta_dict)

    def _get_full_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“全量工作流图 dict”（未裁剪）。

        优先级：
        1) context.workflow_graph（本次请求）
        2) session 进程内缓存
        3) 空图骨架
        """
        workflow_graph = self._to_workflow_graph_dict(self._context.workflow_graph)
        if workflow_graph is not None:
            return workflow_graph

        session_id = self._context.session_id
        cached_workflow_graph = _get_cached_workflow_graph(session_id) if session_id else None
        if cached_workflow_graph is not None:
            return cached_workflow_graph

        return _build_empty_workflow_graph()

    def get_workflow_meta_dict(self) -> Dict[str, str]:
        """
        获取 workflow_meta（工作流名称、描述）。

        优先级：
        1) context.workflow_meta（本次请求）
        2) session 进程内缓存
        3) 空元信息
        """
        workflow_meta = self._to_workflow_meta_dict(self._context.workflow_meta)
        if workflow_meta is not None:
            return workflow_meta

        session_id = self._context.session_id
        cached_workflow_meta = _get_cached_workflow_meta(session_id) if session_id else None
        if cached_workflow_meta is not None:
            return cached_workflow_meta

        return dict(_EMPTY_WORKFLOW_META)

    def get_full_show_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“展示用完整图”（已裁剪）。

        用途：
        - 给大模型/前端展示用，尽量减少无关字段与 token 噪音。
        """
        full_graph = self._get_full_workflow_graph_dict()
        return prune_workflow_graph_for_show(full_graph)

    @staticmethod
    def _to_workflow_graph_dict(workflow_graph_data: Any) -> Dict[str, Any] | None:
        """
        将 workflow_graph 输入归一化为 dict（保留 alias 字段）。
        """
        if workflow_graph_data is None:
            return None
        if hasattr(workflow_graph_data, "model_dump"):
            workflow_graph_dict = workflow_graph_data.model_dump(by_alias=True)
            return workflow_graph_dict if isinstance(workflow_graph_dict, dict) else None
        if isinstance(workflow_graph_data, dict):
            return workflow_graph_data
        return None

    @staticmethod
    def _to_workflow_meta_dict(workflow_meta_data: Any) -> Dict[str, str] | None:
        """
        将 workflow_meta 输入归一化为稳定字典结构。
        """
        if workflow_meta_data is None:
            return None
        if hasattr(workflow_meta_data, "model_dump"):
            workflow_meta_dict = workflow_meta_data.model_dump()
            if not isinstance(workflow_meta_dict, dict):
                return None
            return _normalize_workflow_meta(workflow_meta_dict)
        if isinstance(workflow_meta_data, dict):
            return _normalize_workflow_meta(workflow_meta_data)
        return None


__all__ = [
    "WorkflowGraphCache",
    "_log_tool_result_debug",
    "prune_workflow_graph_for_show",
    "WORKFLOW_GRAPH_PRUNE_RULES",
]
