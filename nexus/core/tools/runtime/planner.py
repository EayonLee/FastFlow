from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.messages.tool import tool_call

from nexus.common.exceptions import BusinessError
from nexus.core.schemas import ChatRequestContext
from nexus.core.tools.runtime.contracts import TOOL_CALL_SOURCE_HINT, ToolCatalog

_HINT_TOOL_MAPPING = (
    ("selected_nodes", "get_workflow_node_summary", "node_id", "节点选择"),
    ("selected_skills", "load_skill", "skill_name", "技能选择"),
)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        normalized_value = str(value or "").strip()
        if not normalized_value or normalized_value in seen_values:
            continue
        seen_values.add(normalized_value)
        deduped_values.append(normalized_value)
    return deduped_values


def _has_workflow_graph_nodes(context: ChatRequestContext) -> bool:
    workflow_graph = context.workflow_graph
    if workflow_graph is None:
        return False
    if hasattr(workflow_graph, "model_dump"):
        workflow_graph = workflow_graph.model_dump(by_alias=True)
    if not isinstance(workflow_graph, dict):
        return False
    nodes = workflow_graph.get("nodes")
    return isinstance(nodes, list) and len(nodes) > 0


def build_hint_tool_message(context: ChatRequestContext, tool_catalog: ToolCatalog) -> AIMessage | None:
    """
    把前端结构化 hints 转成一条 AIMessage(tool_calls)。

    这样后续执行链路与模型产出的 tool_calls 保持完全一致，避免分叉实现。
    """

    execution_hints = context.execution_hints
    if not execution_hints.has_items():
        return None

    tool_calls = []
    for field_name, tool_name, arg_name, hint_label in _HINT_TOOL_MAPPING:
        hint_values = _dedupe_preserve_order(list(getattr(execution_hints, field_name, []) or []))
        if not hint_values:
            continue
        if field_name == "selected_nodes" and not _has_workflow_graph_nodes(context):
            raise BusinessError("selected_nodes requires a non-empty workflow_graph")
        if tool_name not in tool_catalog.registry_by_name:
            raise BusinessError(f"当前智能体未开启{hint_label}所需工具：{tool_name}")
        for hint_value in hint_values:
            tool_calls.append(
                tool_call(
                    name=tool_name,
                    args={arg_name: hint_value},
                    id=f"call_{uuid4().hex}",
                )
            )

    if not tool_calls:
        return None

    return AIMessage(
        content="",
        additional_kwargs={"tool_call_source": TOOL_CALL_SOURCE_HINT},
        tool_calls=tool_calls,
    )
