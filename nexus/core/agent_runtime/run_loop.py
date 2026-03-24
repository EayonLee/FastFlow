from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from nexus.common.exceptions import BusinessError
from nexus.core.agent_runtime.cancellation import RunCancellationContext
from nexus.config.logger import get_logger
from nexus.core.agent_runtime.contracts import (
    AgentRuntimeConfig,
    AgentRuntimeState,
    ModelTurnResult,
)
from nexus.core.agent_runtime.turn_stream import INTERNAL_TURN_RESULT_EVENT, stream_model_turn
from nexus.core.event import (
    PHASE_ANALYZE_QUESTION,
    PHASE_EXECUTE_TOOLS,
    PHASE_GENERATE_FINAL_ANSWER,
    PhaseTracker,
    ToolExecutionTracker,
    build_answer_delta_event,
    build_answer_done_event,
    build_run_completed_event,
    build_run_started_event,
    build_thinking_summary_event,
    is_tool_execution_failed,
)
from nexus.core.history.manager import get_session_history
from nexus.core.tools.runtime.catalog import build_tool_catalog
from nexus.core.tools.runtime.contracts import TOOL_CALL_SOURCE_HINT
from nexus.core.tools.runtime.executor import ToolExecutor
from nexus.core.tools.runtime.planner import build_hint_tool_message

logger = get_logger(__name__)


def _serialize_tool_calls_for_log(tool_calls: list[dict[str, Any]]) -> str:
    serialized_payload = [
        {
            "name": str(tool_call.get("name") or "").strip(),
            "args": tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {},
            "id": str(tool_call.get("id") or "").strip(),
        }
        for tool_call in tool_calls
        if isinstance(tool_call, dict)
    ]
    return json.dumps(serialized_payload, ensure_ascii=False, sort_keys=True)


def _serialize_tool_names_for_log(tool_calls: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            str(tool_call.get("name") or "").strip()
            for tool_call in tool_calls
            if isinstance(tool_call, dict) and str(tool_call.get("name") or "").strip()
        ],
        ensure_ascii=False,
    )


def _resolve_tool_source(message: BaseMessage) -> str:
    source = str((getattr(message, "additional_kwargs", {}) or {}).get("tool_call_source") or "").strip().lower()
    if source == TOOL_CALL_SOURCE_HINT:
        return TOOL_CALL_SOURCE_HINT
    return "model"


def _build_initial_messages(runtime_config: AgentRuntimeConfig, history_messages: list[BaseMessage]) -> list[BaseMessage]:
    return [
        SystemMessage(content=runtime_config.system_prompt),
        *history_messages,
        HumanMessage(content=runtime_config.context.user_prompt),
    ]


def _build_tool_request_events(
    *,
    ai_message: AIMessage,
    phase_tracker: PhaseTracker,
    tool_tracker: ToolExecutionTracker,
) -> list[dict[str, Any]]:
    runtime_events: list[dict[str, Any]] = []
    tool_source = _resolve_tool_source(ai_message)
    selected_message_prefix = "根据已选内容准备工具" if tool_source == TOOL_CALL_SOURCE_HINT else "模型选择工具"

    for tool_call in ai_message.tool_calls or []:
        if not isinstance(tool_call, dict):
            continue
        tool_name = str(tool_call.get("name") or "").strip()
        if not tool_name:
            continue
        runtime_events.extend(
            phase_tracker.transition_to(
                PHASE_EXECUTE_TOOLS,
                "开始执行工具调用",
            )
        )
        tool_tracker.mark_started(tool_call)
        runtime_events.append(
            {
                "type": "tool.selected",
                "tool_name": tool_name,
                "source": tool_source,
                "message": f"{selected_message_prefix}：{tool_name}",
            }
        )
        runtime_events.append(
            {
                "type": "tool.started",
                "tool_name": tool_name,
                "source": tool_source,
                "message": f"开始执行工具：{tool_name}",
            }
        )

    return runtime_events


def _build_tool_result_events(
    *,
    tool_messages: list[ToolMessage],
    tool_tracker: ToolExecutionTracker,
) -> list[dict[str, Any]]:
    runtime_events: list[dict[str, Any]] = []

    for message in tool_messages:
        tool_name = str(getattr(message, "name", "") or "").strip()
        if not tool_name:
            continue
        elapsed_ms = tool_tracker.pop_elapsed_ms(message)
        failed = is_tool_execution_failed(message)
        runtime_events.append(
            {
                "type": "tool.failed" if failed else "tool.completed",
                "tool_name": tool_name,
                "source": _resolve_tool_source(message),
                "status": "failed" if failed else "completed",
                "elapsed_ms": elapsed_ms,
                "message": f"工具执行失败：{tool_name}" if failed else f"工具执行完成：{tool_name}",
            }
        )

    return runtime_events


def _validate_final_answer(turn_result: ModelTurnResult, reasoning_content: str, content: str) -> None:
    if turn_result.message.tool_calls:
        return

    has_answer = bool(str(content or "").strip())
    if has_answer or turn_result.streamed_answer_len > 0:
        return

    logger.error(
        "[模型空回答] stage=%s elapsed_ms=%d tool_choice=%s reasoning_len=%d streamed_reasoning_len=%d",
        turn_result.stage,
        turn_result.elapsed_ms,
        turn_result.tool_choice,
        len(str(reasoning_content or "")),
        turn_result.streamed_reasoning_len,
    )
    raise BusinessError("模型未返回有效回答")


def _raise_if_cancelled(cancellation_context: RunCancellationContext | None) -> None:
    if cancellation_context is not None:
        cancellation_context.raise_if_cancelled()


def build_runtime_state(runtime_config: AgentRuntimeConfig) -> AgentRuntimeState:
    config_id = runtime_config.context.model_config_id
    if not config_id:
        raise BusinessError("缺少模型配置 ID (model_config_id)")

    tool_catalog = build_tool_catalog(runtime_config.context, runtime_config.tool_profile)
    logger.info(
        "[工具目录初始化] agent=%s total=%d workflow=%d skill=%d time=%d",
        runtime_config.agent_name,
        tool_catalog.total_count,
        tool_catalog.workflow_tool_count,
        tool_catalog.skill_tool_count,
        tool_catalog.time_tool_count,
    )

    history = get_session_history(runtime_config.context.session_id)
    return AgentRuntimeState(
        config_id=config_id,
        history=history,
        tool_catalog=tool_catalog,
        history_messages=list(history.messages),
    )


async def run_agent(runtime_config: AgentRuntimeConfig) -> AsyncGenerator[dict[str, Any], None]:
    runtime_state = build_runtime_state(runtime_config)
    cancellation_context = runtime_config.cancellation_context
    tool_executor = ToolExecutor(
        runtime_state.tool_catalog,
        cancellation_context=cancellation_context,
    )
    messages = _build_initial_messages(runtime_config, runtime_state.history_messages)

    final_answer = ""
    last_emitted_thinking = ""
    tool_tracker = ToolExecutionTracker()
    phase_tracker = PhaseTracker(PHASE_ANALYZE_QUESTION, "开始理解用户问题")

    yield build_run_started_event(agent=runtime_config.agent_name)
    for event in phase_tracker.build_start_events():
        yield event

    _raise_if_cancelled(cancellation_context)

    hint_tool_message = build_hint_tool_message(runtime_config.context, runtime_state.tool_catalog)
    if hint_tool_message is not None:
        logger.info(
            "[预选工具调用] agent=%s tool_names=%s",
            runtime_config.agent_name,
            _serialize_tool_names_for_log(list(hint_tool_message.tool_calls or [])),
        )
        logger.debug(
            "[预选工具调用明细] agent=%s tool_calls=%s",
            runtime_config.agent_name,
            _serialize_tool_calls_for_log(list(hint_tool_message.tool_calls or [])),
        )
        messages.append(hint_tool_message)
        for event in _build_tool_request_events(
            ai_message=hint_tool_message,
            phase_tracker=phase_tracker,
            tool_tracker=tool_tracker,
        ):
            yield event
        hint_tool_messages = await tool_executor.execute_ai_message(hint_tool_message)
        messages.extend(hint_tool_messages)
        _raise_if_cancelled(cancellation_context)
        for event in _build_tool_result_events(
            tool_messages=hint_tool_messages,
            tool_tracker=tool_tracker,
        ):
            yield event

    while True:
        _raise_if_cancelled(cancellation_context)
        turn_streamed_answer = ""
        turn_result: ModelTurnResult | None = None

        async for event in stream_model_turn(
            runtime_config=runtime_config,
            config_id=runtime_state.config_id,
            messages=messages,
            tool_catalog=runtime_state.tool_catalog,
        ):
            if event.get("type") == INTERNAL_TURN_RESULT_EVENT:
                internal_result = event.get("result")
                if not isinstance(internal_result, ModelTurnResult):
                    raise BusinessError("模型调用结束后未返回最终结果")
                turn_result = internal_result
                continue

            event_type = str(event.get("type") or "").strip()
            if event_type == "thinking.delta":
                last_emitted_thinking = f"{last_emitted_thinking}{str(event.get('content') or '')}"
                yield event
                continue

            if event_type == "thinking.summary":
                summary_content = str(event.get("content") or "")
                if summary_content and summary_content != last_emitted_thinking:
                    last_emitted_thinking = summary_content
                    yield event
                continue

            if event_type == "answer.delta":
                delta = str(event.get("content") or "")
                if not delta:
                    continue
                turn_streamed_answer = f"{turn_streamed_answer}{delta}"
                for phase_event in phase_tracker.transition_to(
                    PHASE_GENERATE_FINAL_ANSWER,
                    "开始生成最终回答",
                ):
                    yield phase_event
                yield event

        if turn_result is None:
            raise BusinessError("模型调用结束后未返回最终消息")

        _raise_if_cancelled(cancellation_context)
        messages.append(turn_result.message)

        if turn_result.message.tool_calls:
            if turn_streamed_answer:
                yield {"type": "answer.reset"}
            for event in _build_tool_request_events(
                ai_message=turn_result.message,
                phase_tracker=phase_tracker,
                tool_tracker=tool_tracker,
            ):
                yield event
            tool_messages = await tool_executor.execute_ai_message(turn_result.message)
            messages.extend(tool_messages)
            _raise_if_cancelled(cancellation_context)
            for event in _build_tool_result_events(
                tool_messages=tool_messages,
                tool_tracker=tool_tracker,
            ):
                yield event
            continue

        reasoning_content = str(
            (turn_result.message.additional_kwargs or {}).get("reasoning_content") or ""
        ).strip()
        if reasoning_content and reasoning_content != last_emitted_thinking:
            last_emitted_thinking = reasoning_content
            yield build_thinking_summary_event(reasoning_content)

        content = str(turn_result.message.content or turn_streamed_answer or "")
        _validate_final_answer(turn_result, reasoning_content, content)

        if content.startswith(turn_streamed_answer):
            remaining_delta = content[len(turn_streamed_answer):]
        else:
            remaining_delta = content
            if turn_streamed_answer:
                yield {"type": "answer.reset"}

        if remaining_delta:
            for phase_event in phase_tracker.transition_to(
                PHASE_GENERATE_FINAL_ANSWER,
                "开始生成最终回答",
            ):
                yield phase_event
            yield build_answer_delta_event(remaining_delta)

        final_answer = content.strip()
        break

    _raise_if_cancelled(cancellation_context)
    if str(runtime_config.context.user_prompt or "").strip():
        runtime_state.history.add_user_message(runtime_config.context.user_prompt)
    if final_answer:
        runtime_state.history.add_ai_message(final_answer)

    yield phase_tracker.build_completed_event()
    yield build_answer_done_event(final_answer)
    yield build_run_completed_event(final_answer_len=len(final_answer))
    logger.info(
        "[SSE 会话完成] agent=%s final_answer_len=%d",
        runtime_config.agent_name,
        len(final_answer),
    )
