"""
工作流上下文统一读取入口。

本模块只负责三件事：
1. 归一化 workflow_graph / workflow_meta 输入结构
2. 裁剪 workflow_graph（减少无关字段）
3. 提供稳定的读取方法给工具层使用（仅依赖当前请求上下文）
"""

from __future__ import annotations

from typing import Any, Dict, List

from nexus.core.schemas import ChatRequestContext

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


class WorkflowGraphContext:
    """
    workflow_graph / workflow_meta 统一读取入口。
    """

    def __init__(self, context: ChatRequestContext):
        self._context = context

    def _get_full_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“全量工作流图 dict”（未裁剪）。
        """
        workflow_graph = self._to_workflow_graph_dict(self._context.workflow_graph)
        if workflow_graph is not None:
            return workflow_graph

        return _build_empty_workflow_graph()

    def get_workflow_meta_dict(self) -> Dict[str, str]:
        """
        获取 workflow_meta（工作流名称、描述）。
        """
        workflow_meta = self._to_workflow_meta_dict(self._context.workflow_meta)
        if workflow_meta is not None:
            return workflow_meta

        return dict(_EMPTY_WORKFLOW_META)

    def get_full_show_workflow_graph_dict(self) -> Dict[str, Any]:
        """
        获取“展示用完整图”（已裁剪）。
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
    "WorkflowGraphContext",
    "prune_workflow_graph_for_show",
    "WORKFLOW_GRAPH_PRUNE_RULES",
]
