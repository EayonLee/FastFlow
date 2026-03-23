from __future__ import annotations

import json
from functools import partial
from time import perf_counter
from typing import Annotated, Any, AsyncGenerator, Dict, List, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
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
    build_thinking_delta_event,
    build_thinking_summary_event,
    extract_reasoning_from_stream_chunk,
    extract_text_from_stream_content,
    is_tool_execution_failed,
)
from nexus.core.history.manager import get_session_history
from nexus.core.llm import get_llm
from nexus.core.llm.response_normalizer import normalize_answer_and_reasoning
from nexus.core.llm.tool_call_adapter import ensure_tool_call_ids
from nexus.core.policies import resolve_tool_choice, select_tool_candidates
from nexus.core.prompts.chat_prompts import CHAT_SYSTEM_PROMPT
from nexus.core.schemas import ChatRequestContext
from nexus.core.tools import build_skill_tools, build_time_tools, build_workflow_tools
from nexus.core.tools.tool_manager import ToolExecutionManager

NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT = "generate_response_with_tool_context"
NODE_EXECUTE_MODEL_REQUESTED_TOOLS = "execute_model_requested_tools"

logger = get_logger(__name__)


class ChatState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]


class ChatAgent:
    """
    通用对话 Agent（支持按需调用工具）。

    主链路固定为：
    1) 模型决定是否调用工具
    2) 工具执行
    3) 模型基于工具结果生成最终答案
    """

    def __init__(self):
        pass

    @staticmethod
    def _filter_unused_tools(messages: List[BaseMessage], tools: List[Any]) -> List[Any]:
        """
        过滤已经执行过的工具，避免同名工具被重复调用。
        """
        used_tool_names = {
            str(getattr(message, "name", "") or "").strip()
            for message in messages
            if isinstance(message, ToolMessage) and str(getattr(message, "name", "") or "").strip()
        }
        return [tool for tool in tools if str(getattr(tool, "name", "") or "").strip() not in used_tool_names]

    @staticmethod
    def _resolve_generation_stage(messages: List[BaseMessage], generated_response: AIMessage) -> str:
        has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
        if generated_response.tool_calls:
            return "tool_selection_after_tool" if has_tool_result else "tool_selection"
        return "answer_generation_after_tool" if has_tool_result else "answer_generation"

    async def _run_llm_answer(
        self,
        state: ChatState,
        *,
        context: ChatRequestContext,
        config_id: int,
        tools: List[Any],
    ) -> Dict[str, Any]:
        """
        节点：生成回答（必要时发起工具调用）。
        """
        messages = state["messages"]
        candidate_tools = select_tool_candidates(
            context=context,
            messages=messages,
            tools=tools,
        )
        candidate_tools = self._filter_unused_tools(messages, candidate_tools)

        tool_choice = resolve_tool_choice(context, messages)
        logger.info(
            "[模型调用准备完成] 工具候选=%d 工具选择策略=%s",
            len(candidate_tools),
            tool_choice,
        )

        llm, _, model_id = get_llm(
            config_id,
            context.auth_token,
            candidate_tools,
            tool_choice=tool_choice,
        )

        generation_started_at = perf_counter()
        streamed_response = None
        streamed_reasoning = False
        stream_writer = None
        try:
            from langgraph.config import get_stream_writer

            stream_writer = get_stream_writer()
        except Exception:
            stream_writer = None

        async for chunk in llm.astream(list(messages)):
            streamed_response = chunk if streamed_response is None else streamed_response + chunk
            if stream_writer is not None:
                reasoning_delta = extract_reasoning_from_stream_chunk(chunk)
                if reasoning_delta:
                    streamed_reasoning = True
                    stream_writer({"event": "thinking", "text": reasoning_delta})

                delta_text = extract_text_from_stream_content(getattr(chunk, "content", ""))
                if delta_text:
                    stream_writer({"event": "token", "text": delta_text})

        if streamed_response is None:
            generated_response = AIMessage(content="")
        elif isinstance(streamed_response, AIMessage):
            generated_response = streamed_response
        else:
            generated_response = AIMessage(
                content=str(getattr(streamed_response, "content", "") or ""),
                additional_kwargs=dict(getattr(streamed_response, "additional_kwargs", {}) or {}),
                response_metadata=getattr(streamed_response, "response_metadata", {}) or {},
                tool_calls=list(getattr(streamed_response, "tool_calls", []) or []),
                id=getattr(streamed_response, "id", None),
            )
        generated_response = ensure_tool_call_ids(generated_response)

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
        if stream_writer is not None and reasoning_content and not streamed_reasoning:
            stream_writer({"event": "thinking_summary", "text": reasoning_content})

        generation_elapsed_ms = int(max(0, (perf_counter() - generation_started_at) * 1000))
        generation_stage = self._resolve_generation_stage(messages, generated_response)
        logger.info(
            "[模型调用耗时] stage=%s elapsed_ms=%d candidate_tools=%d tool_choice=%s tool_calls=%d answer_len=%d reasoning_len=%d",
            generation_stage,
            generation_elapsed_ms,
            len(candidate_tools),
            tool_choice,
            len(generated_response.tool_calls or []),
            len(str(generated_response.content or "")),
            len(reasoning_content),
        )

        generation_result = "模型发起工具调用" if generated_response.tool_calls else "生成最终回答"
        logger.info(
            "[模型生成结果] 状态=%s content_len=%d",
            generation_result,
            len(str(generated_response.content or "")),
        )

        return {"messages": [generated_response]}

    def _build_app(self, context: ChatRequestContext):
        """
        构建 LangGraph：仅负责节点装配与路由连线。
        """
        config_id = context.model_config_id
        if not config_id:
            raise BusinessError("缺少模型配置 ID (model_config_id)")

        workflow_tools, _ = build_workflow_tools(context)
        skill_tools, _ = build_skill_tools(context)
        time_tools, _ = build_time_tools(context)
        tools = [*workflow_tools, *skill_tools, *time_tools]
        logger.info(
            "[初始化工具成功] 已加载工具总数=%d（workflow=%d,skill=%d,time=%d）",
            len(tools),
            len(workflow_tools),
            len(skill_tools),
            len(time_tools),
        )

        async def generate_node(state: ChatState) -> Dict[str, Any]:
            return await self._run_llm_answer(
                state,
                context=context,
                config_id=config_id,
                tools=tools,
            )

        tool_manager = ToolExecutionManager(tools)

        workflow = StateGraph(ChatState)  # type: ignore[arg-type]
        workflow.add_node(NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT, generate_node)
        workflow.add_node(NODE_EXECUTE_MODEL_REQUESTED_TOOLS, tool_manager.build_execution_node())
        workflow.set_entry_point(NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT)

        def route_after_generation(state: ChatState) -> str:
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return NODE_EXECUTE_MODEL_REQUESTED_TOOLS
            return "__end__"

        workflow.add_conditional_edges(
            NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT,
            route_after_generation,
            {
                NODE_EXECUTE_MODEL_REQUESTED_TOOLS: NODE_EXECUTE_MODEL_REQUESTED_TOOLS,
                "__end__": END,
            },
        )
        workflow.add_edge(NODE_EXECUTE_MODEL_REQUESTED_TOOLS, NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT)

        return workflow.compile()

    async def achat(self, context: ChatRequestContext) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理流式对话请求（按增量文本输出）。
        """
        app = self._build_app(context)
        history = get_session_history(context.session_id)
        state: ChatState = {
            "messages": [
                SystemMessage(content=CHAT_SYSTEM_PROMPT),
                *history.messages,
                HumanMessage(content=context.user_prompt),
            ]
        }

        answer_parts: List[str] = []
        last_emitted = ""
        last_processed_message_count = 0
        last_emitted_thinking = ""
        tool_tracker = ToolExecutionTracker()
        phase_tracker = PhaseTracker(PHASE_ANALYZE_QUESTION, "开始理解用户问题")

        yield build_run_started_event(agent="chat")
        for event in phase_tracker.build_start_events():
            yield event

        async for stream_event in app.astream(state, stream_mode=["custom", "values"]):
            mode = "values"
            update = stream_event
            if isinstance(stream_event, tuple) and len(stream_event) == 2:
                mode, update = stream_event

            if mode == "custom":
                if not isinstance(update, dict):
                    continue
                custom_event = str(update.get("event") or "").strip()
                if custom_event == "token":
                    for event in phase_tracker.transition_to(
                        PHASE_GENERATE_FINAL_ANSWER,
                        "开始生成最终回答",
                    ):
                        yield event
                    delta = str(update.get("text") or "")
                    if not delta:
                        continue
                    answer_parts.append(delta)
                    last_emitted = f"{last_emitted}{delta}"
                    yield build_answer_delta_event(delta)
                    continue
                if custom_event in {"thinking", "thinking_summary"}:
                    delta = str(update.get("text") or "")
                    if not delta:
                        continue
                    if custom_event == "thinking_summary":
                        if delta == last_emitted_thinking:
                            continue
                        last_emitted_thinking = delta
                        yield build_thinking_summary_event(delta)
                        continue
                    last_emitted_thinking = f"{last_emitted_thinking}{delta}"
                    yield build_thinking_delta_event(delta)
                continue

            if mode != "values" or not isinstance(update, dict):
                continue
            messages = update.get("messages")
            if not isinstance(messages, list) or not messages:
                continue
            if len(messages) > last_processed_message_count:
                new_messages = messages[last_processed_message_count:]
                last_processed_message_count = len(messages)
                for message in new_messages:
                    if isinstance(message, AIMessage) and message.tool_calls:
                        for tool_call in message.tool_calls:
                            tool_name = str(tool_call.get("name") or "").strip()
                            if not tool_name:
                                continue
                            for event in phase_tracker.transition_to(
                                PHASE_EXECUTE_TOOLS,
                                "开始执行工具调用",
                            ):
                                yield event
                            tool_tracker.mark_started(tool_call)
                            yield {
                                "type": "tool.selected",
                                "tool_name": tool_name,
                                "message": f"模型选择工具：{tool_name}",
                            }
                            yield {
                                "type": "tool.started",
                                "tool_name": tool_name,
                                "message": f"开始执行工具：{tool_name}",
                            }
                        continue
                    if isinstance(message, ToolMessage):
                        tool_name = str(getattr(message, "name", "") or "").strip()
                        if not tool_name:
                            continue
                        elapsed_ms = tool_tracker.pop_elapsed_ms(message)
                        failed = is_tool_execution_failed(message)
                        logger.info(
                            "[工具执行耗时] tool=%s elapsed_ms=%s status=%s",
                            tool_name,
                            str(elapsed_ms if elapsed_ms is not None else ""),
                            "failed" if failed else "completed",
                        )
                        event_type = "tool.failed" if failed else "tool.completed"
                        message_text = f"工具执行失败：{tool_name}" if failed else f"工具执行完成：{tool_name}"
                        yield {
                            "type": event_type,
                            "tool_name": tool_name,
                            "status": "failed" if failed else "completed",
                            "elapsed_ms": elapsed_ms,
                            "result": str(message.content or ""),
                            "message": message_text,
                        }

            last_message = messages[-1]
            if isinstance(last_message, ToolMessage):
                continue
            if not isinstance(last_message, AIMessage):
                continue
            if last_message.tool_calls:
                continue

            reasoning_content = str(
                (last_message.additional_kwargs or {}).get("reasoning_content") or ""
            ).strip()
            if reasoning_content and reasoning_content != last_emitted_thinking:
                last_emitted_thinking = reasoning_content
                yield build_thinking_summary_event(reasoning_content)

            content = last_message.content or ""
            if not content:
                continue

            if last_emitted and content.startswith(last_emitted):
                delta = content[len(last_emitted) :]
            else:
                delta = content
            if not delta:
                continue

            for event in phase_tracker.transition_to(
                PHASE_GENERATE_FINAL_ANSWER,
                "开始生成最终回答",
            ):
                yield event
            answer_parts.append(delta)
            last_emitted = content
            yield build_answer_delta_event(delta)

        history.add_user_message(context.user_prompt)
        final_answer = "".join(answer_parts).strip()
        if final_answer:
            history.add_ai_message(final_answer)
        yield phase_tracker.build_completed_event()
        yield build_answer_done_event(final_answer)
        yield build_run_completed_event(final_answer_len=len(final_answer))
        logger.info("[会话完成并落库] 回答输出完成 final_answer_len=%d", len(final_answer))
