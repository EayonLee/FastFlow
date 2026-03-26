from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Literal, Optional

TOOL_CALL_SOURCE_HINT = "hint"
TOOL_CALL_SOURCE_MODEL = "model"
ToolCallSource = Literal["hint", "model"]
ToolCapabilityGroup = Literal["workflow", "skill", "time"]
ToolExecutionMode = Literal["inline_async", "isolated_process"]


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
    execution_specs_by_name: Dict[str, "ToolExecutionSpec"] = field(default_factory=dict)
    workflow_tool_count: int = 0
    skill_tool_count: int = 0
    time_tool_count: int = 0
    workflow_tools: list[Any] = field(default_factory=list)
    skill_tools: list[Any] = field(default_factory=list)
    time_tools: list[Any] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.tools)


@dataclass(frozen=True)
class ToolExecutionSpec:
    """
    单个工具的执行规格。

    `inline_async`:
    - 在当前进程内执行
    - 适用于轻量、本地、可取消的工具

    `isolated_process`:
    - 在独立子进程执行
    - 适用于需要强停止保证的阻塞型工具
    """

    tool: Any
    mode: ToolExecutionMode = "inline_async"
    process_target: Optional[Callable[[dict[str, Any]], Any]] = None


CHAT_AGENT_TOOL_PROFILE = AgentToolProfile(
    name="chat",
    enable_workflow_tools=True,
    enable_skill_tools=True,
    enable_time_tools=True,
)
