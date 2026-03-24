from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

TOOL_CALL_SOURCE_HINT = "hint"
TOOL_CALL_SOURCE_MODEL = "model"
ToolCallSource = Literal["hint", "model"]
ToolCapabilityGroup = Literal["workflow", "skill", "time"]


@dataclass(frozen=True)
class AgentToolProfile:
    """
    Agent 可用工具能力开关。

    先保持简单的 capability 开关，不引入额外注册中心复杂度。
    后续其他 agent 只需要声明自己的 profile，即可复用同一套工具 runtime。
    """

    name: str
    enable_workflow_tools: bool = True
    enable_skill_tools: bool = True
    enable_time_tools: bool = True


@dataclass(frozen=True)
class ToolCatalog:
    """
    当前 agent 可用的工具集合与按名称索引。

    说明：
    - `tools` 是暴露给模型的完整工具列表；
    - `*_tools` 保留能力分组视角，避免策略层再维护工具名常量。
    """

    tools: list[Any]
    registry_by_name: Dict[str, Any]
    workflow_tool_count: int = 0
    skill_tool_count: int = 0
    time_tool_count: int = 0
    workflow_tools: list[Any] = field(default_factory=list)
    skill_tools: list[Any] = field(default_factory=list)
    time_tools: list[Any] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.tools)


CHAT_AGENT_TOOL_PROFILE = AgentToolProfile(
    name="chat",
    enable_workflow_tools=True,
    enable_skill_tools=True,
    enable_time_tools=True,
)
