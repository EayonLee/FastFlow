"""
共享工具选择策略。

当前版本刻意保持极简：
- 只决定“当前轮给模型开放哪些工具”
- 只决定“模型是否还允许继续调工具”
- 不再在策略层做 workflow / skill / time 的条件路由

设计原则：
- 已启用工具全部对模型可见
- 真正的安全边界放在执行层与循环保护，而不是关键词猜测
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from nexus.config.config import get_config
from nexus.config.logger import get_logger
from nexus.core.event import is_tool_execution_failed
from nexus.core.tools.runtime.contracts import ToolCatalog

logger = get_logger(__name__)
_settings = get_config()

MAX_TOOL_CALLS_PER_QUESTION = max(1, int(_settings.TOOL_MAX_CALLS_PER_QUESTION))
TOOL_LOOP_WARNING_THRESHOLD = max(1, int(_settings.TOOL_LOOP_WARNING_THRESHOLD))
TOOL_LOOP_CRITICAL_THRESHOLD = max(1, int(_settings.TOOL_LOOP_CRITICAL_THRESHOLD))
TOOL_LOOP_GLOBAL_THRESHOLD = max(1, int(_settings.TOOL_LOOP_GLOBAL_THRESHOLD))
TOOL_LOOP_HISTORY_SIZE = max(1, int(_settings.TOOL_LOOP_HISTORY_SIZE))


@dataclass(frozen=True)
class ToolExecutionRecord:
    """单条工具执行记录。"""

    tool_name: str
    execution_signature: str
    failed: bool


@dataclass(frozen=True)
class ToolLoopCheckResult:
    """工具循环检测结果。"""

    level: str = "none"
    reason: str = ""
    repeat_count: int = 0


def _extract_tool_call_name(raw_call: Any) -> str:
    if isinstance(raw_call, dict):
        return str(raw_call.get("name") or "").strip()
    return str(getattr(raw_call, "name", "") or "").strip()


def _extract_tool_call_args(raw_call: Any) -> dict[str, Any]:
    if isinstance(raw_call, dict):
        raw_args = raw_call.get("args")
        if isinstance(raw_args, dict):
            return raw_args

        function_payload = raw_call.get("function")
        if not isinstance(function_payload, dict):
            return {}

        raw_arguments = function_payload.get("arguments")
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not isinstance(raw_arguments, str):
            return {}

        try:
            parsed = json.loads(raw_arguments)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    raw_args = getattr(raw_call, "args", None)
    return raw_args if isinstance(raw_args, dict) else {}


def build_tool_execution_signature(tool_name: str, tool_args: Any) -> str:
    normalized_name = str(tool_name or "").strip()
    normalized_args = tool_args if isinstance(tool_args, dict) else {}
    normalized_args_json = json.dumps(normalized_args, ensure_ascii=False, sort_keys=True)
    return f"{normalized_name}::{normalized_args_json}"


def get_tool_message_count(messages: Sequence[BaseMessage]) -> int:
    return sum(1 for message in messages if isinstance(message, ToolMessage))


def _iter_recent_tool_execution_records(messages: Sequence[BaseMessage]) -> list[ToolExecutionRecord]:
    pending_calls: Deque[tuple[str, str]] = deque()
    execution_records: list[ToolExecutionRecord] = []

    for message in messages:
        if isinstance(message, AIMessage):
            for raw_call in message.tool_calls or []:
                tool_name = _extract_tool_call_name(raw_call)
                if not tool_name:
                    continue
                tool_args = _extract_tool_call_args(raw_call)
                execution_signature = build_tool_execution_signature(tool_name, tool_args)
                pending_calls.append((tool_name, execution_signature))
            continue

        if not isinstance(message, ToolMessage):
            continue

        tool_name = str(getattr(message, "name", "") or "").strip()
        execution_signature = build_tool_execution_signature(tool_name, {})
        if pending_calls:
            pending_tool_name, pending_signature = pending_calls.popleft()
            if pending_tool_name:
                tool_name = pending_tool_name
            execution_signature = pending_signature

        execution_records.append(
            ToolExecutionRecord(
                tool_name=tool_name,
                execution_signature=execution_signature,
                failed=is_tool_execution_failed(message),
            )
        )

    if len(execution_records) <= TOOL_LOOP_HISTORY_SIZE:
        return execution_records
    return execution_records[-TOOL_LOOP_HISTORY_SIZE:]


def _count_trailing_same_signature(records: Sequence[ToolExecutionRecord]) -> int:
    if not records:
        return 0

    target_signature = records[-1].execution_signature
    repeat_count = 0
    for record in reversed(records):
        if record.execution_signature != target_signature:
            break
        repeat_count += 1
    return repeat_count


def _count_trailing_same_failed_signature(records: Sequence[ToolExecutionRecord]) -> int:
    if not records or not records[-1].failed:
        return 0

    target_signature = records[-1].execution_signature
    repeat_count = 0
    for record in reversed(records):
        if record.execution_signature != target_signature or not record.failed:
            break
        repeat_count += 1
    return repeat_count


def _count_trailing_ping_pong(records: Sequence[ToolExecutionRecord]) -> int:
    if len(records) < 4:
        return 0

    last_two_names = [records[-2].tool_name, records[-1].tool_name]
    if not all(last_two_names) or last_two_names[0] == last_two_names[1]:
        return 0

    allowed_names = {last_two_names[0], last_two_names[1]}
    repeat_count = 0
    expected_index = 1

    for record in reversed(records):
        if record.tool_name not in allowed_names:
            break
        if record.tool_name != last_two_names[expected_index]:
            break
        repeat_count += 1
        expected_index = 1 - expected_index

    return repeat_count


def _build_loop_check_result(reason: str, repeat_count: int) -> ToolLoopCheckResult:
    if repeat_count >= TOOL_LOOP_GLOBAL_THRESHOLD:
        return ToolLoopCheckResult(level="global", reason=reason, repeat_count=repeat_count)
    if repeat_count >= TOOL_LOOP_CRITICAL_THRESHOLD:
        return ToolLoopCheckResult(level="critical", reason=reason, repeat_count=repeat_count)
    if repeat_count >= TOOL_LOOP_WARNING_THRESHOLD:
        return ToolLoopCheckResult(level="warning", reason=reason, repeat_count=repeat_count)
    return ToolLoopCheckResult()


def detect_tool_loop(messages: Sequence[BaseMessage]) -> ToolLoopCheckResult:
    records = _iter_recent_tool_execution_records(messages)
    if not records:
        return ToolLoopCheckResult()

    repeated_failure_result = _build_loop_check_result(
        reason="同一工具与参数连续失败",
        repeat_count=_count_trailing_same_failed_signature(records),
    )
    repeated_signature_result = _build_loop_check_result(
        reason="同一工具与参数被重复执行",
        repeat_count=_count_trailing_same_signature(records),
    )
    ping_pong_result = _build_loop_check_result(
        reason="两个工具之间反复来回切换",
        repeat_count=_count_trailing_ping_pong(records),
    )

    candidates = [repeated_failure_result, repeated_signature_result, ping_pong_result]
    candidates.sort(
        key=lambda item: (
            {"none": 0, "warning": 1, "critical": 2, "global": 3}.get(item.level, 0),
            item.repeat_count,
        ),
        reverse=True,
    )
    return candidates[0]


def select_tool_candidates(tool_catalog: ToolCatalog) -> list[Any]:
    """返回当前 agent 已启用的全部工具。"""
    return list(tool_catalog.tools)


def resolve_tool_choice(
    messages: Sequence[BaseMessage],
    candidate_tools: Sequence[Any],
) -> str:
    """
    统一计算本轮模型调用的 tool_choice。

    规则：
    - 有工具且未触发安全边界时，统一使用 `auto`
    - 无工具或命中循环/上限保护时，返回 `none`
    """

    tool_message_count = get_tool_message_count(messages)
    if tool_message_count >= MAX_TOOL_CALLS_PER_QUESTION:
        logger.info(
            "[工具选择策略] 动作=停止调工具 原因=触发全局安全上限(%d/%d)",
            tool_message_count,
            MAX_TOOL_CALLS_PER_QUESTION,
        )
        return "none"

    tool_loop_check = detect_tool_loop(messages)
    if tool_loop_check.level in {"critical", "global"}:
        logger.info(
            "[工具选择策略] 动作=停止调工具 原因=%s 等级=%s 次数=%d",
            tool_loop_check.reason,
            tool_loop_check.level,
            tool_loop_check.repeat_count,
        )
        return "none"
    if tool_loop_check.level == "warning":
        logger.warning(
            "[工具选择策略] 动作=记录循环告警 原因=%s 等级=%s 次数=%d",
            tool_loop_check.reason,
            tool_loop_check.level,
            tool_loop_check.repeat_count,
        )

    if not candidate_tools:
        logger.info("[工具选择策略] 动作=停止调工具 原因=当前 agent 没有可用工具")
        return "none"

    logger.info("[工具选择策略] 动作=开放全部已启用工具 结果=auto")
    return "auto"
