from __future__ import annotations

import json
from functools import partial
from typing import Annotated, Any, AsyncGenerator, Dict, List, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field, field_validator

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.event import (
    PHASE_ANALYZE_QUESTION,
    PHASE_EXECUTE_TOOLS,
    PHASE_GENERATE_FINAL_ANSWER,
    PHASE_REVIEW_ANSWER,
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
from nexus.core.llm import get_llm
from nexus.core.memory.memory_manager import get_session_history
from nexus.core.policies import (
    MAX_TOOL_CALLS_PER_QUESTION,
    get_tool_message_count,
    requires_workflow_graph_tools,
    resolve_tool_choice,
    select_tool_candidates,
)
from nexus.core.prompts.chat_prompts import (
    CHAT_ANSWER_SUFFICIENCY_REVIEW_PROMPT,
    CHAT_SYSTEM_PROMPT,
)
from nexus.core.prompts.chat_message import build_need_user_input_message, build_review_guidance_message
from nexus.core.schemas import ChatRequestContext
from nexus.core.llm.tool_call_adapter import ensure_tool_call_ids
from nexus.core.tools import build_time_tools, build_workflow_tools

# 三段式流程：生成回答 -> 执行工具 -> 评审充足性。
REVIEW_PENDING_ANSWER_FLAG = "review_pending_answer"
# 单个用户问题在“回答充足性复核”节点最多允许回环的次数。
# 这是复核流程上限，不等于工具调用上限；用于防止复核无法收敛时死循环。
MAX_ANSWER_SUFFICIENCY_REVIEW_ROUNDS = 3

NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT = "generate_response_with_tool_context"
NODE_EXECUTE_MODEL_REQUESTED_TOOLS = "execute_model_requested_tools"
NODE_REVIEW_ANSWER_SUFFICIENCY = "review_answer_sufficiency"

logger = get_logger(__name__)


class AnswerSufficiencyReviewResult(BaseModel):
    """
    review 节点结构化输出协议。

    约束说明：
    - status:
      - sufficient: 当前证据足够，可以直接回答用户
      - need_more_tools: 证据不足，但可通过继续调工具补齐
      - need_user_input: 工具无法补齐，需要用户提供更多信息
    - missing_info: 当前缺失的信息点列表（面向内部与用户提示）
    - suggested_tool_name / suggested_tool_args:
      review 建议优先调用的工具及参数
    - user_guidance: 当需要用户补充信息时，可直接展示的引导语
    """

    status: Literal["sufficient", "need_more_tools", "need_user_input"]
    missing_info: List[str] = Field(default_factory=list)
    suggested_tool_name: str = ""
    suggested_tool_args: Dict[str, Any] = Field(default_factory=dict)
    user_guidance: str = ""

    @field_validator("missing_info", mode="before")
    @classmethod
    def _validate_missing_info(cls, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @field_validator("suggested_tool_name", "user_guidance", mode="before")
    @classmethod
    def _validate_string_fields(cls, value: Any) -> str:
        return str(value or "").strip()

    @field_validator("suggested_tool_args", mode="before")
    @classmethod
    def _validate_tool_args(cls, value: Any) -> Dict[str, Any]:
        return value if isinstance(value, dict) else {}


class ChatState(TypedDict):
    # LangGraph 核心消息状态：按节点增量追加。
    messages: Annotated[List[BaseMessage], add_messages]
    # review 节点生成的内部补证据指令（仅供下一轮模型调用使用，不直接展示给用户）。
    review_guidance: str
    # 当 review 判定“需要继续调工具”时，下一轮强制要求至少一次工具调用。
    force_tool_call: bool
    # 最近一条候选回答是否需要进入 review 审核。
    pending_answer_requires_review: bool
    # review 节点产出的路由动作：answer / call_tool / ask_user。
    sufficiency_review_action: str
    # 已执行的“回答充足性 review”轮次，避免死循环。
    sufficiency_review_count: int


class ChatAgent:
    """
    通用对话 Agent（支持按需调用工具 + 回答充足性复核）。

    主要职责：
    1) 组装系统提示词与历史消息
    2) 按配置构建可执行的 LangGraph
    3) 处理流式对话请求并写入历史
    """

    def __init__(self):
        pass

    @staticmethod
    def _is_review_pending_answer_message(message: BaseMessage) -> bool:
        """
        判断消息是否为“等待 review 审核”的候选回答。

        仅满足以下条件才视为候选回答：
        - 必须是 AIMessage
        - 不能包含 tool_calls（工具调用消息不是最终回答候选）
        - additional_kwargs 中带有 REVIEW_PENDING_ANSWER_FLAG 标记
        """
        if not isinstance(message, AIMessage):
            return False
        if message.tool_calls:
            return False
        return bool((message.additional_kwargs or {}).get(REVIEW_PENDING_ANSWER_FLAG))

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
    def _emit_custom_stream_event(event_type: str, **payload: Any) -> None:
        """向 LangGraph custom stream 写入事件；在非流式上下文中静默忽略。"""
        try:
            from langgraph.config import get_stream_writer

            stream_writer = get_stream_writer()
        except Exception:
            stream_writer = None
        if stream_writer is None:
            return
        event_payload = {"event": event_type}
        event_payload.update(payload)
        stream_writer(event_payload)

    def _build_review_payload(
        self,
        *,
        context: ChatRequestContext,
        messages: List[BaseMessage],
        candidate_answer: AIMessage,
        review_focus_text: str,
        tools: List[Any],
    ) -> Dict[str, Any]:
        """
        构造 review 节点输入：用户问题 + 候选回答 + 全部工具证据 + 候选工具。

        关键点：
        - tool_results 只采集 ToolMessage，确保 review 聚焦“可验证证据”
        - candidate_tools 只放候选工具摘要，避免无关工具干扰决策
        - 同时携带工具预算信息，避免 review 在预算耗尽时仍要求继续调用
        """
        # 收集“已执行工具”的结果，review 仅基于这些可追溯证据判断是否足够回答。
        tool_results = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            normalized_content = str(message.content or "").strip()
            if not normalized_content:
                continue
            tool_results.append(
                {
                    "tool_name": str(getattr(message, "name", "") or ""),
                    "tool_result": normalized_content,
                }
            )

        # 候选工具先做相关性筛选，再做 no_repeat 过滤。
        review_tool_candidates = select_tool_candidates(
            context=context,
            messages=messages,
            tools=tools,
            focus_text=review_focus_text,
        )
        review_tool_candidates = self._filter_unused_tools(messages, review_tool_candidates)
        candidate_tool_summaries = [
            {
                "name": str(getattr(tool, "name", "") or ""),
                "description": str(getattr(tool, "description", "") or ""),
            }
            for tool in review_tool_candidates
        ]

        # 预算字段会直接喂给 review 模型，避免“预算已耗尽却继续建议调工具”。
        used_tool_calls = get_tool_message_count(messages)
        remaining_tool_calls = max(0, MAX_TOOL_CALLS_PER_QUESTION - used_tool_calls)
        return {
            "user_prompt": context.user_prompt,
            "candidate_answer": str(candidate_answer.content or ""),
            "tool_results": tool_results,
            "candidate_tools": candidate_tool_summaries,
            "used_tool_call_count": used_tool_calls,
            "remaining_tool_call_count": remaining_tool_calls,
            "max_tool_call_count": MAX_TOOL_CALLS_PER_QUESTION,
        }

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

        输入（来自状态）：
        - messages: 当前上下文消息序列
        - review_guidance: review 产出的内部补证据指令
        - force_tool_call: 是否强制本轮至少调用一次工具

        输出（写回状态）：
        - messages: 新生成的一条 AIMessage（可能是工具调用，也可能是文本）
        - pending_answer_requires_review: 文本回答是否需要进入 review
        """
        messages = state["messages"]
        review_guidance = str(state.get("review_guidance") or "").strip()
        force_tool_call = bool(state.get("force_tool_call"))
        candidate_tools = select_tool_candidates(
            context=context,
            messages=messages,
            tools=tools,
            focus_text=review_guidance,
        )
        candidate_tools = self._filter_unused_tools(messages, candidate_tools)

        tool_choice = resolve_tool_choice(context, messages)
        # 预算耗尽后，直接关闭工具调用入口，避免无意义循环。
        if get_tool_message_count(messages) >= MAX_TOOL_CALLS_PER_QUESTION:
            tool_choice = "none"
        if force_tool_call and tool_choice != "none":
            tool_choice = "required"
        logger.info(
            "[模型调用准备完成] 工具候选=%d 工具选择策略=%s",
            len(candidate_tools),
            tool_choice,
        )

        # 将候选工具与 tool_choice 一并绑定到当前 LLM 调用。
        llm, llm_adapter = get_llm(
            config_id,
            context.auth_token,
            candidate_tools,
            tool_choice=tool_choice,
        )
        llm_messages: List[BaseMessage] = list(messages)
        if review_guidance:
            # review 指令只作用于当前轮生成，不写入持久历史。
            llm_messages.append(SystemMessage(content=review_guidance))

        should_review_generated_answer = (
            requires_workflow_graph_tools(context.user_prompt)
            or any(isinstance(message, ToolMessage) for message in messages)
        )
        # 统一开启 token 流输出：若后续 review 判定证据不足，会通过 answer_reset 事件撤回候选回答。
        allow_stream_output = True
        stream_writer = None
        try:
            from langgraph.config import get_stream_writer

            stream_writer = get_stream_writer()
        except Exception:
            stream_writer = None

        streamed_response = None
        streamed_reasoning = False
        async for chunk in llm.astream(llm_messages):
            streamed_response = chunk if streamed_response is None else streamed_response + chunk
            if stream_writer is not None:
                reasoning_delta = extract_reasoning_from_stream_chunk(chunk)
                if reasoning_delta:
                    streamed_reasoning = True
                    stream_writer({"event": "thinking", "text": reasoning_delta})
            if stream_writer is None or not allow_stream_output:
                continue
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

        answer_content, reasoning_content = llm_adapter.split_response_content(
            generated_response.content,
            additional_kwargs=generated_response.additional_kwargs,
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

        pending_review = False
        if not generated_response.tool_calls and should_review_generated_answer:
            # 只有“文本回答”才有 review 意义；工具调用消息由工具节点处理。
            additional_kwargs = dict(generated_response.additional_kwargs or {})
            additional_kwargs[REVIEW_PENDING_ANSWER_FLAG] = True
            generated_response = AIMessage(
                content=generated_response.content,
                additional_kwargs=additional_kwargs,
                response_metadata=generated_response.response_metadata,
                tool_calls=generated_response.tool_calls,
                id=generated_response.id,
            )
            pending_review = True
        if generated_response.tool_calls:
            generation_result = "模型发起工具调用"
        elif pending_review:
            generation_result = "生成候选回答，进入充足性复核"
        else:
            generation_result = "生成最终回答"
        logger.info(
            "[模型生成结果] 状态=%s content_len=%d",
            generation_result,
            len(str(generated_response.content or "")),
        )

        return {
            "messages": [generated_response],
            "review_guidance": "",
            "force_tool_call": False,
            "pending_answer_requires_review": pending_review,
        }

    def _run_review_answer_sufficiency(
        self,
        state: ChatState,
        *,
        context: ChatRequestContext,
        config_id: int,
        tools: List[Any],
    ) -> Dict[str, Any]:
        """
        节点：评审当前回答是否满足用户问题。

        该节点负责“质量闸门”：
        - sufficient: 放行候选回答
        - need_more_tools: 回到生成节点继续补证据
        - need_user_input: 终止工具循环并引导用户补充信息
        """
        messages = state["messages"]
        review_count = int(state.get("sufficiency_review_count") or 0)
        if review_count >= MAX_ANSWER_SUFFICIENCY_REVIEW_ROUNDS:
            # 防止循环不收敛，超轮次后直接转“请补充信息”。
            user_guidance = build_need_user_input_message(missing_info=[])
            logger.warning("[回答充足性复核] 达到最大轮次，改为引导用户补充信息")
            self._emit_custom_stream_event(
                "answer_reset",
                message="候选回答未通过审查，已切换为用户补充引导",
            )
            return {
                "messages": [AIMessage(content=user_guidance)],
                "pending_answer_requires_review": False,
                "sufficiency_review_action": "ask_user",
                "sufficiency_review_count": review_count,
                "review_guidance": "",
                "force_tool_call": False,
            }

        if not state.get("pending_answer_requires_review"):
            return {
                "pending_answer_requires_review": False,
                "sufficiency_review_action": "answer",
                "sufficiency_review_count": review_count,
            }

        pending_answer: AIMessage | None = None
        for message in reversed(messages):
            if self._is_review_pending_answer_message(message):
                pending_answer = message
                break

        if pending_answer is None:
            return {
                "pending_answer_requires_review": False,
                "sufficiency_review_action": "answer",
                "sufficiency_review_count": review_count,
            }

        review_payload = self._build_review_payload(
            context=context,
            messages=messages,
            candidate_answer=pending_answer,
            review_focus_text=str(state.get("review_guidance") or ""),
            tools=tools,
        )

        try:
            # 使用结构化输出
            review_llm, _ = get_llm(config_id, context.auth_token)
            review_llm = review_llm.with_structured_output(AnswerSufficiencyReviewResult)
            raw_review_result = review_llm.invoke(
                [
                    SystemMessage(content=CHAT_ANSWER_SUFFICIENCY_REVIEW_PROMPT),
                    HumanMessage(content=json.dumps(review_payload, ensure_ascii=False)),
                ]
            )
            if isinstance(raw_review_result, AnswerSufficiencyReviewResult):
                review_result_model = raw_review_result
            elif isinstance(raw_review_result, dict):
                review_result_model = AnswerSufficiencyReviewResult.model_validate(raw_review_result)
            else:
                raise ValueError("invalid review result type")
        except Exception:  # noqa: BLE001
            logger.exception(
                "对话执行.ChatAgent._run_review_answer_sufficiency.调用复核模型失败 "
                "review_round=%d",
                review_count,
            )
            review_result_model = AnswerSufficiencyReviewResult(
                status="need_user_input",
                user_guidance="",
            )

        review_result = review_result_model.model_dump()
        review_status = review_result_model.status
        candidate_tool_names = {
            str(item.get("name") or "").strip()
            for item in review_payload["candidate_tools"]
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

        if review_status == "need_more_tools" and review_payload["remaining_tool_call_count"] <= 0:
            # 预算耗尽后，不再继续调工具，直接走用户补充。
            review_status = "need_user_input"

        if review_status == "need_more_tools" and not review_payload["candidate_tools"]:
            # 无可用候选工具时，继续调工具没有意义。
            review_status = "need_user_input"

        suggested_tool_name = str(review_result.get("suggested_tool_name") or "").strip()
        if review_status == "need_more_tools" and suggested_tool_name not in candidate_tool_names:
            # review 建议了不在候选集内的工具，视为不可执行。
            review_status = "need_user_input"
            if not str(review_result.get("user_guidance") or "").strip():
                review_result["user_guidance"] = build_need_user_input_message(missing_info=[])

        if review_status == "sufficient":
            # 去掉 pending 标记后输出最终答案。
            logger.info(
                "[回答充足性复核] 结果=证据充足，直接回答 review_round=%d",
                review_count,
            )
            finalized_answer_kwargs = dict(pending_answer.additional_kwargs or {})
            finalized_answer_kwargs.pop(REVIEW_PENDING_ANSWER_FLAG, None)
            finalized_answer = AIMessage(
                content=str(pending_answer.content or ""),
                additional_kwargs=finalized_answer_kwargs,
                response_metadata=pending_answer.response_metadata,
                id=pending_answer.id,
            )
            return {
                "messages": [finalized_answer],
                "pending_answer_requires_review": False,
                "sufficiency_review_action": "answer",
                "sufficiency_review_count": review_count + 1,
                "review_guidance": "",
                "force_tool_call": False,
            }

        if review_status == "need_more_tools":
            # 生成下一轮内部指令，并强制下一轮优先调工具补证据。
            logger.info(
                "[回答充足性复核] 结果=证据不足，继续调工具 建议工具=%s review_round=%d",
                suggested_tool_name,
                review_count,
            )
            self._emit_custom_stream_event(
                "answer_reset",
                message="候选回答未通过审查，继续调用工具补充证据",
            )
            review_guidance = build_review_guidance_message(
                missing_info=review_result.get("missing_info") or [],
                suggested_tool_name=str(review_result.get("suggested_tool_name") or "").strip(),
                suggested_tool_args=review_result.get("suggested_tool_args") or {},
            )
            return {
                "pending_answer_requires_review": False,
                "sufficiency_review_action": "call_tool",
                "sufficiency_review_count": review_count + 1,
                "review_guidance": review_guidance,
                "force_tool_call": True,
            }

        missing_info = review_result.get("missing_info") or []
        user_guidance = build_need_user_input_message(
            missing_info=missing_info,
            user_guidance=str(review_result.get("user_guidance") or ""),
        )
        self._emit_custom_stream_event(
            "answer_reset",
            message="候选回答未通过审查，当前需要用户补充信息",
        )
        logger.info(
            "[回答充足性复核] 结果=工具无法补齐证据，转为用户补充 missing_info=%d review_round=%d",
            len(missing_info),
            review_count,
        )
        return {
            "messages": [AIMessage(content=user_guidance)],
            "pending_answer_requires_review": False,
            "sufficiency_review_action": "ask_user",
            "sufficiency_review_count": review_count + 1,
            "review_guidance": "",
            "force_tool_call": False,
        }

    def _build_app(self, context: ChatRequestContext):
        """
        构建 LangGraph：仅负责节点装配与路由连线。

        这里不写业务判断，业务逻辑全部下沉到各节点执行方法中。
        """
        config_id = context.model_config_id
        if not config_id:
            raise BusinessError("缺少模型配置 ID (model_config_id)")

        # 组合工具集
        workflow_tools, _ = build_workflow_tools(context)
        time_tools, _ = build_time_tools(context)
        tools = [*workflow_tools, *time_tools]
        logger.info(
            "[初始化工具成功] 已加载工具总数=%d（workflow=%d,time=%d）",
            len(tools),
            len(workflow_tools),
            len(time_tools),
        )

        async def generate_node(state: ChatState) -> Dict[str, Any]:
            return await self._run_llm_answer(
                state,
                context=context,
                config_id=config_id,
                tools=tools,
            )
        execute_tools_node = ToolNode(tools)
        review_node = partial(
            self._run_review_answer_sufficiency,
            context=context,
            config_id=config_id,
            tools=tools,
        )

        # StateGraph(ChatState) 表示整张图共享同一份状态结构（消息 + review 控制字段）。
        # 某些类型检查器会对 TypedDict + 泛型推断误报，这里显式忽略静态告警，不影响运行时类型安全。
        workflow = StateGraph(ChatState)  # type: ignore[arg-type]
        # 注册三个执行节点：生成回答 -> 执行工具 -> 复核回答。
        # 这里的工具执行节点使用 LangGraph 官方 ToolNode，避免手写工具调度细节。
        workflow.add_node(NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT, generate_node)
        workflow.add_node(NODE_EXECUTE_MODEL_REQUESTED_TOOLS, execute_tools_node)
        workflow.add_node(NODE_REVIEW_ANSWER_SUFFICIENCY, review_node)

        # 入口固定为“生成回答”节点，所有流程都从模型首轮决策开始。
        workflow.set_entry_point(NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT)

        def route_after_generation(state: ChatState) -> str:
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return NODE_EXECUTE_MODEL_REQUESTED_TOOLS
            if state.get("pending_answer_requires_review"):
                return NODE_REVIEW_ANSWER_SUFFICIENCY
            return "__end__"

        def route_after_review(state: ChatState) -> str:
            if str(state.get("sufficiency_review_action") or "") == "call_tool":
                return NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT
            return "__end__"

        # 生成节点分叉：
        # - 调工具 -> tools 节点
        # - 文本待复核 -> review 节点
        # - 其他 -> 结束
        workflow.add_conditional_edges(
            NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT,
            route_after_generation,
            {
                NODE_EXECUTE_MODEL_REQUESTED_TOOLS: NODE_EXECUTE_MODEL_REQUESTED_TOOLS,
                NODE_REVIEW_ANSWER_SUFFICIENCY: NODE_REVIEW_ANSWER_SUFFICIENCY,
                "__end__": END,
            },
        )
        # 工具执行完后回到生成节点，基于工具结果继续推理。
        workflow.add_edge(NODE_EXECUTE_MODEL_REQUESTED_TOOLS, NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT)
        # review 节点分叉：
        # - 仍需补证据 -> 回生成节点
        # - 已足够回答 或 需用户补充 -> 结束
        workflow.add_conditional_edges(
            NODE_REVIEW_ANSWER_SUFFICIENCY,
            route_after_review,
            {
                NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT: NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT,
                "__end__": END,
            },
        )

        # 返回可执行图实例，供流式会话调用。
        return workflow.compile()

    async def achat(self, context: ChatRequestContext) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理流式对话请求（按增量文本输出）。

        实现要点：
        - 对外统一输出“事件对象”，前端可解耦渲染“执行过程”和“最终回答”
        - review pending 的候选回答不会直接对用户展示
        - 最终将用户问题与最终回答写回会话历史
        """
        app = self._build_app(context)
        history = get_session_history(context.session_id)
        state: ChatState = {
            "messages": [
                SystemMessage(content=CHAT_SYSTEM_PROMPT),
                *history.messages,
                HumanMessage(content=context.user_prompt),
            ],
            "review_guidance": "",
            "force_tool_call": False,
            "pending_answer_requires_review": False,
            "sufficiency_review_action": "answer",
            "sufficiency_review_count": 0,
        }

        answer_parts: List[str] = []
        last_emitted = ""
        last_processed_message_count = 0
        review_started_emitted = False
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
                if custom_event == "answer_reset":
                    answer_parts.clear()
                    last_emitted = ""
                    yield {
                        "type": "answer.reset",
                        "message": str(update.get("message") or "候选回答未通过审查，继续补充信息"),
                    }
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
            if self._is_review_pending_answer_message(last_message):
                if not review_started_emitted:
                    review_started_emitted = True
                    for event in phase_tracker.transition_to(
                        PHASE_REVIEW_ANSWER,
                        "开始复核回答充足性",
                    ):
                        yield event
                    yield {
                        "type": "review.started",
                        "message": "正在复核回答是否满足用户问题",
                    }
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
                # 处理“全量重发”型流输出，只取新增增量。
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

        # 先记录本轮用户问题，保持会话历史完整可追溯。
        history.add_user_message(context.user_prompt)
        # 流式输出是分片增量，需要在结束时拼成一条完整答案再落库。
        final_answer = "".join(answer_parts).strip()
        if final_answer:
            # 仅落库最终可见答案，避免把中间候选稿写入历史。
            history.add_ai_message(final_answer)
        yield phase_tracker.build_completed_event()
        yield build_answer_done_event(final_answer)
        yield build_run_completed_event(final_answer_len=len(final_answer))
        logger.info("[会话完成并落库] 回答输出完成 final_answer_len=%d", len(final_answer))
