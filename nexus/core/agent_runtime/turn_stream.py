from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from nexus.common.exceptions import BusinessError
from nexus.core.agent_runtime.cancellation import await_with_cancellation
from nexus.config.config import get_config
from nexus.config.logger import get_logger
from nexus.core.agent_runtime.contracts import AgentRuntimeConfig, ModelTurnResult
from nexus.core.event import (
    build_answer_delta_event,
    build_thinking_delta_event,
    build_thinking_summary_event,
    extract_reasoning_from_stream_chunk,
    extract_text_from_stream_content,
)
from nexus.core.llm import get_llm
from nexus.core.llm.response_normalizer import InlineThinkingStreamParser, normalize_answer_and_reasoning
from nexus.core.llm.tool_call_adapter import ensure_tool_call_ids
from nexus.core.policies import resolve_tool_choice, select_tool_candidates
from nexus.core.tools.runtime.contracts import ToolCatalog

logger = get_logger(__name__)
settings = get_config()

INTERNAL_TURN_RESULT_EVENT = "_agent_runtime.turn_result"

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


def _build_ai_message_from_stream(streamed_response: Any) -> AIMessage:
    if streamed_response is None:
        return AIMessage(content="")
    if isinstance(streamed_response, AIMessage):
        return streamed_response
    return AIMessage(
        content=str(getattr(streamed_response, "content", "") or ""),
        additional_kwargs=dict(getattr(streamed_response, "additional_kwargs", {}) or {}),
        response_metadata=getattr(streamed_response, "response_metadata", {}) or {},
        tool_calls=list(getattr(streamed_response, "tool_calls", []) or []),
        id=getattr(streamed_response, "id", None),
    )


def _resolve_generation_stage(messages: list[BaseMessage], generated_response: AIMessage) -> str:
    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
    if generated_response.tool_calls:
        if has_tool_result:
            return "tool_selection_after_tool"
        return "tool_selection"
    if has_tool_result:
        return "answer_generation_after_tool"
    return "answer_generation"


def _get_stream_wait_timeout(
    *,
    generation_started_at: float,
    first_event_seen: bool,
) -> float:
    """
    统一计算单轮流式调用的下一次等待时长。

    这里不再区分 thinking / 非 thinking 模型。
    这里的超时判定语义是“首个流式事件”。
    与“首个可见 Token 输出”分开定义，避免把协议层超时和展示层体验指标混在一起。
    """
    elapsed_seconds = perf_counter() - generation_started_at
    remaining_total = float(settings.MODEL_STREAM_TOTAL_TIMEOUT_SECONDS) - elapsed_seconds
    if remaining_total <= 0:
        raise BusinessError("模型流式输出超时：整轮总时长已超限")

    phase_timeout = (
        float(settings.MODEL_STREAM_IDLE_TIMEOUT_SECONDS)
        if first_event_seen
        else float(settings.MODEL_STREAM_FIRST_EVENT_TIMEOUT_SECONDS)
    )
    return max(0.001, min(phase_timeout, remaining_total))


async def _close_async_iterator(async_iterator: Any) -> None:
    close_method = getattr(async_iterator, "aclose", None)
    if callable(close_method):
        try:
            await close_method()
        except Exception:
            logger.debug("Failed to close async stream iterator cleanly.", exc_info=True)


async def stream_model_turn(
    *,
    runtime_config: AgentRuntimeConfig,
    config_id: int,
    messages: list[BaseMessage],
    tool_catalog: ToolCatalog,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    执行一轮模型流式调用。

    该函数只负责：
    - 读取当前 agent 可用的完整工具目录
    - 实时转发模型增量事件
    - 产出一条结构化的单轮结果
    """

    cancellation_context = runtime_config.cancellation_context
    if cancellation_context is not None:
        cancellation_context.raise_if_cancelled()

    candidate_tools = select_tool_candidates(tool_catalog)
    tool_choice = resolve_tool_choice(messages, candidate_tools)
    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)

    logger.info(
        "[模型请求开始] agent=%s stage=%s candidate_count=%d tool_choice=%s",
        runtime_config.agent_name,
        "after_tool" if has_tool_result else "initial",
        len(candidate_tools),
        tool_choice,
    )

    llm, _, model_id = get_llm(
        config_id,
        runtime_config.context.auth_token,
        candidate_tools,
        tool_choice=tool_choice,
    )

    generation_started_at = perf_counter()
    streamed_response = None
    streamed_answer_text = ""
    streamed_reasoning_text = ""
    first_event_seen = False
    first_visible_output_seen = False
    inline_thinking_parser = InlineThinkingStreamParser()
    stream_iterator = llm.astream(list(messages)).__aiter__()

    def _mark_first_visible_output(kind: str) -> None:
        nonlocal first_visible_output_seen
        if first_visible_output_seen:
            return
        first_visible_output_seen = True
        logger.info(
            "[模型首个可见Token输出] agent=%s kind=%s elapsed_ms=%d",
            runtime_config.agent_name,
            kind,
            int(max(0, (perf_counter() - generation_started_at) * 1000)),
        )

    try:
        while True:
            wait_timeout = _get_stream_wait_timeout(
                generation_started_at=generation_started_at,
                first_event_seen=first_event_seen,
            )
            try:
                chunk = await await_with_cancellation(
                    stream_iterator.__anext__(),
                    cancellation_context=cancellation_context,
                    timeout=wait_timeout,
                )
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError as error:
                if first_event_seen:
                    raise BusinessError("模型流式输出超时：长时间未收到新的流式事件") from error
                raise BusinessError("模型流式输出超时：首个流式事件返回过慢") from error

            first_event_seen = True
            streamed_response = chunk if streamed_response is None else streamed_response + chunk

            delta_text = extract_text_from_stream_content(getattr(chunk, "content", ""))
            parsed_answer_delta, inline_reasoning_delta = inline_thinking_parser.feed(delta_text)
            reasoning_delta = extract_reasoning_from_stream_chunk(chunk) or inline_reasoning_delta

            if reasoning_delta:
                _mark_first_visible_output("thinking")
                streamed_reasoning_text = f"{streamed_reasoning_text}{reasoning_delta}"
                yield build_thinking_delta_event(reasoning_delta)

            if parsed_answer_delta:
                _mark_first_visible_output("answer")
                streamed_answer_text = f"{streamed_answer_text}{parsed_answer_delta}"
                yield build_answer_delta_event(parsed_answer_delta)

            if cancellation_context is not None:
                cancellation_context.raise_if_cancelled()
    finally:
        await _close_async_iterator(stream_iterator)

    if cancellation_context is not None:
        cancellation_context.raise_if_cancelled()

    remaining_answer_delta, remaining_reasoning_delta = inline_thinking_parser.flush()
    if remaining_reasoning_delta:
        _mark_first_visible_output("thinking")
        streamed_reasoning_text = f"{streamed_reasoning_text}{remaining_reasoning_delta}"
        yield build_thinking_delta_event(remaining_reasoning_delta)
    if remaining_answer_delta:
        _mark_first_visible_output("answer")
        streamed_answer_text = f"{streamed_answer_text}{remaining_answer_delta}"
        yield build_answer_delta_event(remaining_answer_delta)

    generated_response = ensure_tool_call_ids(_build_ai_message_from_stream(streamed_response))
    answer_content, reasoning_content = normalize_answer_and_reasoning(
        generated_response.content,
        generated_response.additional_kwargs,
        model_id=model_id,
    )

    additional_kwargs = dict(generated_response.additional_kwargs or {})
    if reasoning_content:
        additional_kwargs["reasoning_content"] = reasoning_content
    if answer_content != str(generated_response.content or "") or reasoning_content:
        generated_response = AIMessage(
            content=answer_content,
            additional_kwargs=additional_kwargs,
            response_metadata=generated_response.response_metadata,
            tool_calls=generated_response.tool_calls,
            id=generated_response.id,
        )

    if reasoning_content and not streamed_reasoning_text:
        yield build_thinking_summary_event(reasoning_content)

    generation_elapsed_ms = int(max(0, (perf_counter() - generation_started_at) * 1000))
    generation_stage = _resolve_generation_stage(messages, generated_response)
    answer_len = len(str(generated_response.content or ""))
    reasoning_len = len(reasoning_content)

    logger.info(
        "[模型响应完成] agent=%s stage=%s elapsed_ms=%d candidate_count=%d tool_choice=%s tool_calls=%d answer_len=%d reasoning_len=%d",
        runtime_config.agent_name,
        generation_stage,
        generation_elapsed_ms,
        len(candidate_tools),
        tool_choice,
        len(generated_response.tool_calls or []),
        answer_len,
        reasoning_len,
    )

    if generated_response.tool_calls:
        tool_names = [
            str(tool_call.get("name") or "").strip()
            for tool_call in generated_response.tool_calls
            if isinstance(tool_call, dict) and str(tool_call.get("name") or "").strip()
        ]
        logger.info(
            "[模型产出工具调用] agent=%s tool_names=%s",
            runtime_config.agent_name,
            json.dumps(tool_names, ensure_ascii=False),
        )
        logger.debug(
            "[模型产出工具调用明细] agent=%s tool_calls=%s",
            runtime_config.agent_name,
            _serialize_tool_calls_for_log(list(generated_response.tool_calls or [])),
        )
    else:
        logger.info(
            "[模型产出最终回答] agent=%s content_len=%d",
            runtime_config.agent_name,
            answer_len,
        )

    yield {
        "type": INTERNAL_TURN_RESULT_EVENT,
        "result": ModelTurnResult(
            message=generated_response,
            candidate_tool_count=len(candidate_tools),
            tool_choice=tool_choice,
            elapsed_ms=generation_elapsed_ms,
            stage=generation_stage,
            answer_len=answer_len,
            reasoning_len=reasoning_len,
            streamed_answer_len=len(streamed_answer_text),
            streamed_reasoning_len=len(streamed_reasoning_text),
        ),
    }
