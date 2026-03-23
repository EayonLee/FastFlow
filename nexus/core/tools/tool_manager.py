"""
通用工具执行管理器。

职责边界：
1) 对“模型已经决定调用工具”的消息做执行前清洗（同轮重复调用去重）。
2) 返回可直接挂到 LangGraph 节点的 runnable（官方执行链路）。

不负责：
- 工具候选筛选
- tool_choice 决策

说明：
- 这里不手动调用 `ToolNode.ainvoke(...)`，而是把 `ToolNode` 作为图节点的一部分返回。
- 这样可避免程序化二次调用时的 config 注入不稳定问题。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode

from nexus.config.logger import get_logger
from nexus.core.policies import build_tool_execution_signature

logger = get_logger(__name__)


def _dedupe_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    对同一条 AIMessage 中的工具调用做去重。

    这里只去掉“同名工具 + 相同参数”的完全重复调用，不处理跨轮重复。
    跨轮是否允许继续调用，由策略层统一决定；执行层只负责避免模型单轮重复刷同一个请求。
    """

    deduped_tool_calls: List[Dict[str, Any]] = []
    seen_signatures: set[str] = set()

    for tool_call in tool_calls:
        tool_name = str(tool_call.get("name") or "").strip()
        tool_args = tool_call.get("args")
        execution_signature = build_tool_execution_signature(tool_name, tool_args)
        if execution_signature in seen_signatures:
            continue
        seen_signatures.add(execution_signature)
        deduped_tool_calls.append(tool_call)

    return deduped_tool_calls


def _build_tool_call_payload(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """
    把标准化后的 tool_call 回写到 additional_kwargs["tool_calls"]。

    LangGraph 的 ToolNode 在多数场景下只依赖 `message.tool_calls`，但这里同步回写
    `additional_kwargs`，是为了保持消息对象前后结构一致，避免调试时出现“显式字段已变、
    原始 provider payload 没变”的困惑。
    """

    tool_args = tool_call.get("args")
    return {
        "id": tool_call.get("id"),
        "type": "function",
        "function": {
            "name": tool_call.get("name"),
            "arguments": json.dumps(tool_args if isinstance(tool_args, dict) else {}, ensure_ascii=False),
        },
    }


class ToolExecutionManager:
    """
    通用工具执行管理器。

    设计目标：
    - 复用 LangGraph 官方 `ToolNode` 的执行能力
    - 在真正执行前增加一层“同轮完全重复调用去重”
    - 让各类 Agent 只负责流程编排，不再在 agent 文件中堆工具执行细节
    """

    def __init__(self, tools: List[Any]):
        self._tool_executor = ToolNode(tools)

    def _sanitize_state_before_execution(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        工具执行前的状态清洗：
        - 仅处理最后一条 AIMessage 的 tool_calls
        - 去掉同名+同参数的完全重复调用
        """
        messages = state.get("messages")
        if not isinstance(messages, list) or not messages:
            return state

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return state

        deduped_tool_calls = _dedupe_tool_calls(last_message.tool_calls)
        removed_count = len(last_message.tool_calls) - len(deduped_tool_calls)
        if removed_count <= 0:
            return state

        logger.warning("[工具管理] action=dedupe_duplicate_calls removed_count=%d", removed_count)

        updated_kwargs = dict(last_message.additional_kwargs or {})
        updated_kwargs["tool_calls"] = [_build_tool_call_payload(tool_call) for tool_call in deduped_tool_calls]
        sanitized_last_message = AIMessage(
            content=last_message.content,
            additional_kwargs=updated_kwargs,
            response_metadata=last_message.response_metadata,
            tool_calls=deduped_tool_calls,
            id=last_message.id,
        )
        sanitized_state = dict(state)
        sanitized_state["messages"] = [*messages[:-1], sanitized_last_message]
        return sanitized_state

    def build_execution_node(self):
        """
        返回可直接挂到 StateGraph 的工具执行节点 runnable。

        执行链路：
        1) 先做状态清洗（去重）
        2) 再进入官方 ToolNode 执行工具
        """
        preprocessor = RunnableLambda(
            self._sanitize_state_before_execution,
            name="sanitize_tool_calls_before_execution",
        )
        return preprocessor | self._tool_executor
