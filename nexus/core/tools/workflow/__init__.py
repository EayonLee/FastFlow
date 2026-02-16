"""
工作流图工具包。

该包聚合所有与 workflow_graph（前端导出 JSON）相关的工具。对外统一入口为
`build_workflow_graph_tools`，会合并返回：
- 基础读图工具（base_tools）
- 业务语义工具（例如 MCP 工具清单抽取：mcp_tools）

设计目标：
- base 工具保持通用与稳定，避免夹杂具体业务语义。
- 业务语义抽取逻辑单独拆模块，便于按节点类型扩展，不让 base 膨胀成大杂烩。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from nexus.core.schemas import ChatRequestContext

from .base_tools import WorkflowGraphTools, build_workflow_graph_tools as build_workflow_graph_base_tools
from .mcp_node_tools import WorkflowGraphMcpTools, build_workflow_graph_mcp_tools


@dataclass
class WorkflowGraphToolSuite:
    """
    除 LangChain 可调用工具外，同时返回实现对象集合，便于：
    - 代码内部直接调用
    - 单元测试复用实现逻辑

    base：通用读图工具实现
    mcp：MCP 工具清单抽取工具实现
    """

    base: WorkflowGraphTools
    mcp: WorkflowGraphMcpTools


def build_workflow_graph_tools(context: ChatRequestContext) -> Tuple[List, WorkflowGraphToolSuite]:
    """
    构建工作流图工具列表（供 chat/builder agent 使用）。

    返回：
    - tools：暴露给大模型的 LangChain 工具列表
    - suite：实现对象集合（便于代码/测试直接调用）
    """

    base_tools, base_impl = build_workflow_graph_base_tools(context)
    mcp_tools, mcp_impl = build_workflow_graph_mcp_tools(context)
    return [*base_tools, *mcp_tools], WorkflowGraphToolSuite(base=base_impl, mcp=mcp_impl)


__all__ = [
    "WorkflowGraphTools",
    "WorkflowGraphMcpTools",
    "WorkflowGraphToolSuite",
    "build_workflow_graph_tools",
]
