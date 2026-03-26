"""
共享 agent runtime 的轻量公共入口。

这里刻意避免在包初始化阶段导入 `run_loop`、`turn_stream` 这类重模块。
否则工具执行器引用 `nexus.core.agent_runtime.cancellation` 时，会先触发包初始化，
再反向导入 `run_loop -> executor`，形成循环依赖。
"""

from nexus.core.agent_runtime.cancellation import RunCancellationContext, RunCancelledError
from nexus.core.agent_runtime.contracts import AgentRuntimeConfig, AgentRuntimeState, ModelTurnResult
from nexus.core.agent_runtime.registry import active_run_registry

INTERNAL_TURN_RESULT_EVENT = "_agent_runtime.turn_result"


def build_runtime_state(*args, **kwargs):
    from nexus.core.agent_runtime.run_loop import build_runtime_state as _build_runtime_state

    return _build_runtime_state(*args, **kwargs)


def run_agent(*args, **kwargs):
    from nexus.core.agent_runtime.run_loop import run_agent as _run_agent

    return _run_agent(*args, **kwargs)


def stream_model_turn(*args, **kwargs):
    from nexus.core.agent_runtime.turn_stream import stream_model_turn as _stream_model_turn

    return _stream_model_turn(*args, **kwargs)


__all__ = [
    "AgentRuntimeConfig",
    "AgentRuntimeState",
    "ModelTurnResult",
    "RunCancellationContext",
    "RunCancelledError",
    "active_run_registry",
    "INTERNAL_TURN_RESULT_EVENT",
    "build_runtime_state",
    "run_agent",
    "stream_model_turn",
]
