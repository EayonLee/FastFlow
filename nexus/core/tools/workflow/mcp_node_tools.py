"""
工作流图 MCP 相关工具（高层、确定性抽取）。

背景：
- 工作流编排画布通过 `tools` 与 `toolSet` 节点接入 MCP 能力，并通过 `edges` 表示挂载关系。
- 大模型最容易在“工具清单”这类问题上产生臆测（补工具名、改描述、漏条目）。
  因此这里所有抽取都必须确定性执行：严格从 workflow_graph 的原始字段中取值。

提供能力：
- `get_toolset_tools`：抽取 `toolSet` 节点的 `toolList`（严格原文）。
- `get_tools_node_mcp_tools`：从 `tools` 节点沿出边找到下挂的 `toolSet`，合并其 `toolList`（严格原文）。

输出设计：
- 保持与现有工具一致：返回值为 JSON 字符串。
- 同时返回结构化 `items` 与后端渲染好的 `markdown_table`，避免大模型对字段做二次改写。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

from .cache import WorkflowGraphCache, _log_tool_result_debug

logger = get_logger(__name__)


@dataclass
class ResolvedNode:
    """
    从工作流图解析出来的“目标节点”。

    说明：
    - raw 保留原始 dict，后续抽取 inputs/toolSetData/toolList 时需要依赖原始结构。
    """

    node_id: str
    flow_node_type: str
    name: str
    raw: Dict[str, Any]


class WorkflowGraphMcpTools:
    """
    工作流图 MCP 相关高层工具（确定性抽取，避免模型臆测）：
    - toolSet: 抽取其 MCP toolList
    - tools: 沿边找到下挂 toolSet，再汇总 MCP toolList
    """

    def __init__(self, context: ChatRequestContext):
        self._context = context
        # 与 base_tools 共用缓存策略：本次请求优先，其次 session 进程内兜底缓存。
        self._cache = WorkflowGraphCache(context)
        self._cache.cache_if_present()

    def _resolve_node(self, node_id_or_name: str) -> Tuple[Optional[ResolvedNode], Optional[Dict[str, Any]]]:
        """
        返回 (ResolvedNode, error_json)。error_json 不为 None 表示未命中或命中不唯一。
        """
        needle = str(node_id_or_name or "").strip()
        if not needle:
            return None, {"error": "node_id_or_name is empty"}

        graph = self._cache.get_full_show_workflow_graph_dict()
        nodes = graph.get("nodes", [])
        if not isinstance(nodes, list):
            return None, {"error": "workflow_graph.nodes is not a list"}

        # 1) nodeId 精确匹配优先（最稳定、无歧义）。
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if str(node.get("nodeId") or "") == needle:
                return (
                    ResolvedNode(
                        node_id=str(node.get("nodeId") or ""),
                        flow_node_type=str(node.get("flowNodeType") or ""),
                        name=str(node.get("name") or ""),
                        raw=node,
                    ),
                    None,
                )

        # 2) name 模糊匹配（包含）。若命中多个，返回候选，禁止默认选择第一个。
        needle_cf = needle.casefold()
        candidates: List[ResolvedNode] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "")
            if needle_cf and needle_cf in name.casefold():
                candidates.append(
                    ResolvedNode(
                        node_id=str(node.get("nodeId") or ""),
                        flow_node_type=str(node.get("flowNodeType") or ""),
                        name=name,
                        raw=node,
                    )
                )

        if not candidates:
            return None, {"error": f"node not found: {needle}"}
        if len(candidates) > 1:
            return None, {
                "error": f"node name is ambiguous: {needle}",
                "candidates": [{"nodeId": c.node_id, "flowNodeType": c.flow_node_type, "name": c.name} for c in candidates],
            }
        return candidates[0], None

    def _extract_tool_list_from_toolset_node(self, toolset_node: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        """
        兼容两种常见形态：
        1) inputs[key=="toolSetData"].value.toolList
        2) inputs[].value.toolSetData.toolList
        返回 (tool_list, extraction_path_used)。
        """
        inputs = toolset_node.get("inputs", [])
        if not isinstance(inputs, list):
            return [], "inputs(not_list)"

        # 形态 1（优先）：inputs[key="toolSetData"].value.toolList
        for item in inputs:
            if not isinstance(item, dict):
                continue
            if item.get("key") != "toolSetData":
                continue
            value = item.get("value")
            if not isinstance(value, dict):
                continue
            tool_list = value.get("toolList")
            if isinstance(tool_list, list):
                return [t for t in tool_list if isinstance(t, dict)], "inputs[key=toolSetData].value.toolList"

        # 形态 2（兼容）：inputs[].value.toolSetData.toolList
        for item in inputs:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if not isinstance(value, dict):
                continue
            toolset_data = value.get("toolSetData")
            if not isinstance(toolset_data, dict):
                continue
            tool_list = toolset_data.get("toolList")
            if isinstance(tool_list, list):
                return [t for t in tool_list if isinstance(t, dict)], "inputs[].value.toolSetData.toolList"

        return [], "toolList(not_found)"

    def _render_tool_list_markdown(self, tool_list: List[Dict[str, Any]]) -> str:
        """
        将 toolList 渲染为 Markdown 表格。

        说明：工具清单必须“原封不动”输出，因此在后端直接渲染，避免大模型二次改写。
        """
        lines = ["| 序号 | 工具名称 | 描述 |", "|---:|---|---|"]
        for idx, tool_item in enumerate(tool_list, start=1):
            name = str(tool_item.get("name") or "")
            desc = str(tool_item.get("description") or "")
            # 避免换行导致表格断行。
            name = name.replace("\n", " ").strip()
            desc = desc.replace("\n", " ").strip()
            lines.append(f"| {idx} | {name} | {desc} |")
        return "\n".join(lines)

    def get_toolset_tools(self, node_id_or_name: str) -> str:
        """
        工具：给定 toolSet 节点（nodeId 或 name），返回其 MCP toolList。

        要求：
        - items 必须是 toolList 原文投影（name/description/inputSchema），禁止翻译/改写/补全。
        """
        logger.info("Agent tool [get_toolset_tools] - start. node=%s session_id=%s", node_id_or_name, self._context.session_id)
        resolved, error = self._resolve_node(node_id_or_name)
        if error:
            result_json = json.dumps(error, ensure_ascii=False)
            logger.info("Agent tool [get_toolset_tools] - done. ok=false session_id=%s", self._context.session_id)
            _log_tool_result_debug("get_toolset_tools", self._context.session_id, result_json)
            return result_json

        if resolved.flow_node_type != "toolSet":
            error = {
                "error": "node is not a toolSet",
                "node": {"nodeId": resolved.node_id, "flowNodeType": resolved.flow_node_type, "name": resolved.name},
            }
            result_json = json.dumps(error, ensure_ascii=False)
            logger.info("Agent tool [get_toolset_tools] - done. ok=false session_id=%s", self._context.session_id)
            _log_tool_result_debug("get_toolset_tools", self._context.session_id, result_json)
            return result_json

        tool_list, path_used = self._extract_tool_list_from_toolset_node(resolved.raw)
        # 严格按原文字段投影输出，禁止改写。
        result = {
            "toolSet": {"nodeId": resolved.node_id, "flowNodeType": resolved.flow_node_type, "name": resolved.name},
            "count": len(tool_list),
            "extraction_path_used": path_used,
            "items": [
                {
                    "name": t.get("name"),
                    "description": t.get("description"),
                    "inputSchema": t.get("inputSchema"),
                }
                for t in tool_list
            ],
            "markdown_table": self._render_tool_list_markdown(tool_list),
        }
        result_json = json.dumps(result, ensure_ascii=False)
        logger.info(
            "Agent tool [get_toolset_tools] - done. ok=true count=%d session_id=%s",
            len(tool_list),
            self._context.session_id,
        )
        _log_tool_result_debug("get_toolset_tools", self._context.session_id, result_json)
        return result_json

    def get_tools_node_mcp_tools(self, node_id_or_name: str, handle: Optional[str] = None) -> str:
        """
        工具：给定 tools 节点（nodeId 或 name），返回其下挂 toolSet 暴露的 MCP toolList 并集。

        handle 说明：
        - 如果传入 handle，则只统计 sourceHandle 匹配的连线。
        """
        logger.info(
            "Agent tool [get_tools_node_mcp_tools] - start. node=%s handle=%s session_id=%s",
            node_id_or_name,
            handle,
            self._context.session_id,
        )
        resolved, error = self._resolve_node(node_id_or_name)
        if error:
            result_json = json.dumps(error, ensure_ascii=False)
            logger.info("Agent tool [get_tools_node_mcp_tools] - done. ok=false session_id=%s", self._context.session_id)
            _log_tool_result_debug("get_tools_node_mcp_tools", self._context.session_id, result_json)
            return result_json

        if resolved.flow_node_type != "tools":
            error = {
                "error": "node is not a tools node",
                "node": {"nodeId": resolved.node_id, "flowNodeType": resolved.flow_node_type, "name": resolved.name},
            }
            result_json = json.dumps(error, ensure_ascii=False)
            logger.info("Agent tool [get_tools_node_mcp_tools] - done. ok=false session_id=%s", self._context.session_id)
            _log_tool_result_debug("get_tools_node_mcp_tools", self._context.session_id, result_json)
            return result_json

        graph = self._cache.get_full_show_workflow_graph_dict()
        edges = graph.get("edges", [])
        nodes = graph.get("nodes", [])
        if not isinstance(edges, list) or not isinstance(nodes, list):
            error = {"error": "workflow_graph.edges/nodes is not a list"}
            result_json = json.dumps(error, ensure_ascii=False)
            logger.info("Agent tool [get_tools_node_mcp_tools] - done. ok=false session_id=%s", self._context.session_id)
            _log_tool_result_debug("get_tools_node_mcp_tools", self._context.session_id, result_json)
            return result_json

        # 建立 nodeId -> node 的索引，便于遍历 edges 时快速定位目标节点。
        node_by_id: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("nodeId") or "")
            if node_id:
                node_by_id[node_id] = node

        toolset_nodes: List[ResolvedNode] = []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if str(edge.get("source") or "") != resolved.node_id:
                continue
            # handle 是可选过滤条件：提供则必须精确匹配。
            if handle and str(edge.get("sourceHandle") or "") != str(handle):
                continue
            target_id = str(edge.get("target") or "")
            target_node = node_by_id.get(target_id)
            if not isinstance(target_node, dict):
                continue
            # 只把下游的 toolSet 作为 MCP 工具来源。
            if str(target_node.get("flowNodeType") or "") != "toolSet":
                continue
            toolset_nodes.append(
                ResolvedNode(
                    node_id=target_id,
                    flow_node_type="toolSet",
                    name=str(target_node.get("name") or ""),
                    raw=target_node,
                )
            )

        all_items: List[Dict[str, Any]] = []
        toolset_summaries: List[Dict[str, Any]] = []
        for ts in toolset_nodes:
            # 每个 toolSet 独立抽取，并记录抽取路径（证据字段）。
            tool_list, path_used = self._extract_tool_list_from_toolset_node(ts.raw)
            toolset_summaries.append(
                {
                    "nodeId": ts.node_id,
                    "name": ts.name,
                    "count": len(tool_list),
                    "extraction_path_used": path_used,
                }
            )
            all_items.extend(tool_list)

        result = {
            "toolsNode": {"nodeId": resolved.node_id, "flowNodeType": resolved.flow_node_type, "name": resolved.name},
            "handle": (str(handle).strip() if handle is not None and str(handle).strip() else None),
            "toolSets": toolset_summaries,
            "count": len(all_items),
            "items": [
                {"name": t.get("name"), "description": t.get("description"), "inputSchema": t.get("inputSchema")}
                for t in all_items
            ],
            "markdown_table": self._render_tool_list_markdown(all_items),
        }
        result_json = json.dumps(result, ensure_ascii=False)
        logger.info(
            "Agent tool [get_tools_node_mcp_tools] - done. ok=true toolset_count=%d count=%d session_id=%s",
            len(toolset_nodes),
            len(all_items),
            self._context.session_id,
        )
        _log_tool_result_debug("get_tools_node_mcp_tools", self._context.session_id, result_json)
        return result_json


def build_workflow_graph_mcp_tools(context: ChatRequestContext) -> Tuple[List, WorkflowGraphMcpTools]:
    """
    构建 workflow_graph 的 MCP 相关工具列表。

    返回：
    - tools：LangChain 工具列表
    - tool_impl：实现对象
    """
    tool_impl = WorkflowGraphMcpTools(context)

    @tool
    def get_toolset_tools(node_id_or_name: str):
        # 该工具做确定性抽取，并在后端渲染 markdown_table，避免大模型改写工具清单。
        """工作流图工具：获取指定 toolSet 节点（MCP工具清单节点）暴露的 MCP 工具清单（严格原文抽取）。"""
        return tool_impl.get_toolset_tools(node_id_or_name)

    @tool
    def get_tools_node_mcp_tools(node_id_or_name: str, handle: Optional[str] = None):
        # 该工具沿 tools 节点出边找到下挂 toolSet，再合并 toolList（严格原文抽取）。
        """工作流图工具：获取指定 tools 节点（MCP智能调度节点）下挂的 toolSet 的 MCP 工具清单（严格原文抽取）。"""
        return tool_impl.get_tools_node_mcp_tools(node_id_or_name, handle=handle)

    return [get_toolset_tools, get_tools_node_mcp_tools], tool_impl
