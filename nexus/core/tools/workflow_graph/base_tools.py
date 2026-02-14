"""
工作流图基础工具（通用读图能力）。

该模块只提供与节点类型无关的通用能力：
- 获取完整工作流图（展示用裁剪版本）
- 按 nodeId 获取单个节点信息
- 按关键词检索节点（name/type/intro/nodeId）

注意：
- 这里不要写业务语义抽取（例如 MCP toolList 抽取），业务语义应放到独立模块
  例如 `mcp_tools.py`，避免 base 工具膨胀。
"""

from __future__ import annotations

import json
from typing import List, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

from .cache import WorkflowGraphCache, _log_tool_result_debug

logger = get_logger(__name__)


class WorkflowGraphTools:
    """
    工作流图工具：
    1) 查询完整工作流图
    2) 查询单个节点详情
    3) 按关键词检索节点

    调用链路：
    - 外层通过 build_workflow_graph_tools 注册 LangChain tool
    - tool 调用本类公开方法
    - 公开方法统一通过 get_full_show_workflow_graph_dict 取图数据
    """

    def __init__(self, context: ChatRequestContext):
        # 当前请求上下文，包含 session_id / workflow_graph 等字段。
        self.context = context
        # 统一的 workflow_graph 读取入口（本次请求优先 + session 缓存兜底）。
        self._cache = WorkflowGraphCache(context)
        # 初始化时尝试把本次请求图写入缓存，便于后续请求复用。
        self._cache.cache_if_present()

    def get_full_workflow_graph(self) -> str:
        """
        工作流图工具：返回完整工作流图 JSON。
        """
        logger.info("Agent tool [get_full_workflow_graph] - start. session_id=%s", self.context.session_id)
        full_workflow_graph = self._cache.get_full_show_workflow_graph_dict()
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
        full_workflow_graph = self._cache.get_full_show_workflow_graph_dict()
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
            _log_tool_result_debug("find_workflow_graph_nodes", self.context.session_id, empty_result_json)
            return empty_result_json

        full_workflow_graph = self._cache.get_full_show_workflow_graph_dict()
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
        # 该输出会被大模型直接消费，因此必须保持 key 稳定（nodes/edges/chatConfig）。
        """工作流图工具：获取当前工作流图完整结构，包含：节点完整信息、节点连线拓扑关系、全局配置。"""
        return tool_impl.get_full_workflow_graph()

    @tool
    def get_workflow_node_info(node_id: str):
        # 节点详情会以归一化结构返回（id/type/name/intro/inputs/outputs），便于前端统一渲染。
        """工作流图工具：根据节点 ID 获取节点详情。"""
        return tool_impl.get_workflow_node_info(node_id)

    @tool
    def find_workflow_graph_nodes(query: str):
        # 关键词检索为尽力而为，可能返回多个候选。
        """工作流图工具：按关键词检索节点。"""
        return tool_impl.find_workflow_graph_nodes(query)

    # 返回固定顺序，便于调试与观测。
    return [
        get_full_workflow_graph,
        get_workflow_node_info,
        find_workflow_graph_nodes,
    ], tool_impl
