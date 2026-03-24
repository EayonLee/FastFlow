from __future__ import annotations

from typing import Any

from nexus.core.schemas import ChatRequestContext
from nexus.core.tools.runtime.contracts import AgentToolProfile, ToolCatalog
from nexus.core.tools.system.skill_tools import build_skill_tools
from nexus.core.tools.system.time_tools import build_time_tools
from nexus.core.tools.workflow import build_workflow_tools


def _register_tools(registry_by_name: dict[str, Any], tools: list[Any]) -> None:
    for tool in tools:
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not tool_name:
            continue
        if tool_name in registry_by_name:
            raise ValueError(f"duplicate tool registered: {tool_name}")
        registry_by_name[tool_name] = tool


def build_tool_catalog(context: ChatRequestContext, profile: AgentToolProfile) -> ToolCatalog:
    """
    按 agent profile 构建可用工具清单。
    """

    workflow_tools: list[Any] = []
    skill_tools: list[Any] = []
    time_tools: list[Any] = []

    if profile.enable_workflow_tools:
        workflow_tools, _ = build_workflow_tools(context)
    if profile.enable_skill_tools:
        skill_tools, _ = build_skill_tools(context)
    if profile.enable_time_tools:
        time_tools, _ = build_time_tools(context)

    tools = [*workflow_tools, *skill_tools, *time_tools]
    registry_by_name: dict[str, Any] = {}
    _register_tools(registry_by_name, tools)

    return ToolCatalog(
        tools=tools,
        registry_by_name=registry_by_name,
        workflow_tools=workflow_tools,
        skill_tools=skill_tools,
        time_tools=time_tools,
        workflow_tool_count=len(workflow_tools),
        skill_tool_count=len(skill_tools),
        time_tool_count=len(time_tools),
    )
