from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage

from nexus.core.agent_runtime.cancellation import RunCancellationContext
from nexus.core.schemas import ChatRequestContext
from nexus.core.tools.runtime.contracts import AgentToolProfile, ToolCatalog


@dataclass(frozen=True)
class AgentRuntimeConfig:
    """
    共享 Agent Runtime 的最小配置。

    当前只保留 chat 已经稳定需要的字段，避免为未来 agent 过度抽象。
    """

    agent_name: str
    context: ChatRequestContext
    system_prompt: str
    tool_profile: AgentToolProfile
    supports_workflow_context: bool = True
    cancellation_context: RunCancellationContext | None = None


@dataclass(frozen=True)
class ModelTurnResult:
    """
    单轮模型调用的最终结果。

    `stream_model_turn()` 会先逐块产出流式事件，再在结尾补这一份结构化结果，
    供上层决定“继续调工具”还是“结束本轮回答”。
    """

    message: AIMessage
    candidate_tool_count: int
    tool_choice: str
    elapsed_ms: int
    stage: str
    answer_len: int
    reasoning_len: int
    streamed_answer_len: int
    streamed_reasoning_len: int


@dataclass(frozen=True)
class AgentRuntimeState:
    """
    共享 runtime 在单次请求内维护的执行状态。

    这里保存的都是“一个请求期间会被多轮复用”的对象，避免在每轮模型调用前重复构造。
    """

    config_id: int
    history: Any
    tool_catalog: ToolCatalog
    history_messages: list[Any]
