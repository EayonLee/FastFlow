"""
工作流图基础工具（通用读图能力）。

该模块只提供与节点类型无关的通用能力：
- 获取完整工作流图（展示用裁剪版本）
- 获取工作流元信息（workflow_name / workflow_description）
- 按 nodeId 获取轻量节点摘要
- 按 nodeId 获取单个节点信息
- 按关键词检索节点（name/type/intro/nodeId）

注意：
- 这里不要写业务语义抽取（例如 MCP toolList 抽取），业务语义应放到独立模块
  例如 `mcp_node_tools.py`，避免 base 工具膨胀。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger, log_tool_failure, log_tool_success
from nexus.core.schemas import ChatRequestContext
from .context import WorkflowGraphContext

logger = get_logger(__name__)

_SUMMARY_CONFIG_KEYS = {"model", "temperature", "maxToken"}


def _has_configured_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _build_input_field_summary(item: dict) -> dict:
    return {
        "key": item.get("key"),
        "label": item.get("label"),
        "valueType": item.get("valueType"),
        "required": bool(item.get("required", False)),
        "has_value": _has_configured_value(item.get("value")),
    }


def _build_output_field_summary(item: dict) -> dict:
    return {
        "key": item.get("key"),
        "label": item.get("label"),
        "valueType": item.get("valueType"),
    }


def _build_node_config_summary(inputs: list[dict], outputs: list[dict]) -> dict:
    summary = {
        "input_count": len(inputs),
        "output_count": len(outputs),
    }

    for item in inputs:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        value = item.get("value")

        if key in _SUMMARY_CONFIG_KEYS and isinstance(value, (str, int, float, bool)):
            summary[key] = value
            continue
        if key == "history":
            summary["history_enabled"] = _has_configured_value(value)
            if isinstance(value, int):
                summary["history_rounds"] = value
            continue
        if key == "systemPrompt":
            summary["has_system_prompt"] = _has_configured_value(value)
            continue
        if key == "fileUrlList":
            summary["has_files"] = _has_configured_value(value)
            continue
        if key == "userChatInput":
            summary["reads_user_input"] = _has_configured_value(value)
            continue
        if key == "isResponseAnswerText" and isinstance(value, bool):
            summary["returns_answer_text"] = value
            continue
        if key == "aiChatVision" and isinstance(value, bool):
            summary["vision_enabled"] = value

    return summary


class WorkflowGraphTools:
    """
    工作流图工具：
    1) 查询完整工作流图
    2) 查询工作流元信息
    3) 查询节点轻量摘要
    4) 查询单个节点详情
    5) 按关键词检索节点

    调用链路：
    - 外层通过 build_workflow_base_tools 注册 LangChain tool
    - tool 调用本类公开方法
    - 公开方法统一通过 get_full_show_workflow_graph_dict 取图数据
    """

    def __init__(self, context: ChatRequestContext):
        # 当前请求上下文，包含 session_id / workflow_graph 等字段。
        self.context = context
        # 统一的 workflow_graph 读取入口（只读当前请求上下文）。
        self._context_reader = WorkflowGraphContext(context)

    def get_full_workflow_graph(self) -> str:
        """
        工作流图工具：返回完整工作流图 JSON。
        """
        full_workflow_graph = self._context_reader.get_full_show_workflow_graph_dict()
        result_json = json.dumps(full_workflow_graph, ensure_ascii=False)
        log_tool_success(
            logger,
            "get_full_workflow_graph",
            nodes=len(full_workflow_graph.get("nodes", [])),
            edges=len(full_workflow_graph.get("edges", [])),
        )
        return result_json

    def get_workflow_meta(self) -> str:
        """
        工作流图工具：返回工作流元信息 JSON。
        """
        workflow_meta = self._context_reader.get_workflow_meta_dict()
        result_json = json.dumps(workflow_meta, ensure_ascii=False)
        log_tool_success(
            logger,
            "get_workflow_meta",
            workflow_name=str(workflow_meta.get("workflow_name") or ""),
            has_description=bool(str(workflow_meta.get("workflow_description") or "").strip()),
        )
        return result_json

    def get_workflow_node_info(self, node_id: str) -> str:
        """
        工作流图工具：按节点 ID 查询节点详情。

        返回结构与节点检索接口一致，便于前端统一渲染。
        """
        full_workflow_graph = self._context_reader.get_full_show_workflow_graph_dict()
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            # 规范化输出字段，便于前端/调用方统一渲染。
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
                log_tool_success(
                    logger,
                    "get_workflow_node_info",
                    node_id=str(workflow_graph_node.get("id") or ""),
                    node_type=str(workflow_graph_node.get("type") or ""),
                    name=str(workflow_graph_node.get("name") or ""),
                )
                return result_json
        # 未命中时返回统一错误结构。
        error_result = {"error": f"node not found: {node_id}"}
        error_result_json = json.dumps(error_result, ensure_ascii=False)
        log_tool_failure(logger, "get_workflow_node_info", error=str(error_result.get("error") or ""), node_id=node_id)
        return error_result_json

    def get_workflow_node_summary(self, node_id: str) -> str:
        """
        工作流图工具：按节点 ID 返回轻量节点摘要。

        该摘要仅保留模型总结所需的结构化信息，不返回超长配置原文。
        """
        full_workflow_graph = self._context_reader.get_full_show_workflow_graph_dict()
        for node in full_workflow_graph.get("nodes", []):
            if not isinstance(node, dict):
                continue
            if str(node.get("nodeId") or "") != node_id:
                continue

            raw_inputs = node.get("inputs")
            raw_outputs = node.get("outputs")
            inputs = [item for item in raw_inputs if isinstance(item, dict)] if isinstance(raw_inputs, list) else []
            outputs = [item for item in raw_outputs if isinstance(item, dict)] if isinstance(raw_outputs, list) else []
            workflow_graph_node_summary = {
                "id": node.get("nodeId"),
                "type": node.get("flowNodeType"),
                "name": node.get("name"),
                "intro": node.get("intro"),
                "input_fields": [_build_input_field_summary(item) for item in inputs],
                "output_fields": [_build_output_field_summary(item) for item in outputs],
                "config_summary": _build_node_config_summary(inputs, outputs),
            }
            result_json = json.dumps(workflow_graph_node_summary, ensure_ascii=False)
            log_tool_success(
                logger,
                "get_workflow_node_summary",
                node_id=str(workflow_graph_node_summary.get("id") or ""),
                node_type=str(workflow_graph_node_summary.get("type") or ""),
                name=str(workflow_graph_node_summary.get("name") or ""),
                input_count=len(workflow_graph_node_summary.get("input_fields", [])),
                output_count=len(workflow_graph_node_summary.get("output_fields", [])),
            )
            return result_json

        error_result = {"error": f"node not found: {node_id}"}
        error_result_json = json.dumps(error_result, ensure_ascii=False)
        log_tool_failure(logger, "get_workflow_node_summary", error=str(error_result.get("error") or ""), node_id=node_id)
        return error_result_json

    def find_workflow_graph_nodes(self, query: str) -> str:
        """
        工作流图工具：按关键词检索节点（name/type/intro）。

        说明：检索不区分大小写；仅对 name/type/intro 三个字段做包含匹配。
        """
        # 统一清洗输入，避免空格和大小写影响匹配结果。
        query_text = (query or "").strip().lower()
        if not query_text:
            empty_result_json = json.dumps([], ensure_ascii=False)
            log_tool_success(logger, "find_workflow_graph_nodes", query=str(query or "").strip(), hits=0)
            return empty_result_json

        full_workflow_graph = self._context_reader.get_full_show_workflow_graph_dict()
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
        log_tool_success(
            logger,
            "find_workflow_graph_nodes",
            query=str(query or "").strip(),
            hits=len(matched_nodes),
        )
        return result_json

def build_workflow_base_tools(context: ChatRequestContext) -> Tuple[List, WorkflowGraphTools]:
    """
    工作流图工具：构建工具列表（Chat/Builder 都可复用）。

    返回：
    - tools: 提供给 LangChain 的可调用工具列表
    - tool_impl: 具体实现对象（便于外层在需要时直接调用）
    """
    tool_impl = WorkflowGraphTools(context)

    @tool
    def get_full_workflow_graph():
        """
        在需要分析当前工作流整体结构时调用（节点、连线、上下游、拓扑）。
        返回完整工作流 JSON：`nodes`、`edges`、`chatConfig`。
        仅询问工作流名称/描述时，优先使用 `get_workflow_meta`。
        """
        return tool_impl.get_full_workflow_graph()

    @tool
    def get_workflow_meta():
        """
        在只需要工作流名称或描述时调用。
        返回稳定结构：`workflow_name`、`workflow_description`。
        不返回节点明细与连线拓扑。
        """
        return tool_impl.get_workflow_meta()

    @tool
    def get_workflow_node_info(node_id: str):
        """
        在已知 `node_id` 且需要完整节点配置时调用。
        输入必须是节点 ID；返回 `id/type/name/intro/inputs/outputs`。
        若节点不存在，返回 `{"error": "..."}"`。
        """
        return tool_impl.get_workflow_node_info(node_id)

    @tool
    def get_workflow_node_summary(node_id: str):
        """
        在已知 `node_id` 且只需要节点摘要时调用。
        返回轻量结构：`id/type/name/intro/input_fields/output_fields/config_summary`。
        不返回完整 `systemPrompt`、文件列表或其他超长配置原文。
        """
        return tool_impl.get_workflow_node_summary(node_id)

    @tool
    def find_workflow_graph_nodes(query: str):
        """
        在不知道 `node_id`、仅有关键词时调用（节点名/类型/用途）。
        输入 `query` 会模糊匹配 `nodeId/name/intro/flowNodeType`，返回候选节点数组。
        若 `query` 为空，返回空数组 `[]`。
        """
        return tool_impl.find_workflow_graph_nodes(query)

    tools = [
        get_full_workflow_graph,
        get_workflow_meta,
        get_workflow_node_summary,
        get_workflow_node_info,
        find_workflow_graph_nodes,
    ]
    # 返回固定顺序，便于调试与观测。
    return tools, tool_impl
