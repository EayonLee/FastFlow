"""
共享工具执行器。

设计目标：
- 让工具执行过程显式、可日志化、可超时控制；
- 让不同 agent 复用同一套工具执行语义；
- 保持执行层简单，不在这里混入工具选择策略。
"""

from __future__ import annotations

import asyncio
import json
from time import perf_counter
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from nexus.config.config import get_config
from nexus.config.logger import get_logger
from nexus.core.agent_runtime.cancellation import RunCancellationContext, await_with_cancellation
from nexus.core.policies import build_tool_execution_signature
from nexus.core.tools.runtime.contracts import (
    TOOL_CALL_SOURCE_MODEL,
    ToolCallSource,
    ToolCatalog,
)

logger = get_logger(__name__)
settings = get_config()


def _normalize_tool_args(raw_args: Any) -> dict[str, Any]:
    return raw_args if isinstance(raw_args, dict) else {}


def _serialize_tool_calls_for_log(tool_calls: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                "id": str(tool_call.get("id") or "").strip(),
                "name": str(tool_call.get("name") or "").strip(),
                "args": _normalize_tool_args(tool_call.get("args")),
            }
            for tool_call in tool_calls
        ],
        ensure_ascii=False,
        sort_keys=True,
    )


def _serialize_tool_names_for_log(tool_calls: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            str(tool_call.get("name") or "").strip()
            for tool_call in tool_calls
            if str(tool_call.get("name") or "").strip()
        ],
        ensure_ascii=False,
    )


def _serialize_tool_output(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, (dict, list)):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _serialize_tool_args_for_log(tool_args: dict[str, Any]) -> str:
    return json.dumps(tool_args, ensure_ascii=False, sort_keys=True)


def _build_error_tool_message(
    *,
    tool_name: str,
    tool_call_id: str,
    source: ToolCallSource,
    error_message: str,
) -> ToolMessage:
    return ToolMessage(
        content=json.dumps({"error": error_message}, ensure_ascii=False),
        tool_call_id=tool_call_id,
        name=tool_name,
        status="error",
        additional_kwargs={"tool_call_source": source},
    )


class ToolExecutor:
    """
    显式工具执行器。

    职责：
    - 对 AIMessage.tool_calls 做同轮去重
    - 顺序执行工具并产出 ToolMessage
    - 在统一位置处理日志、超时、未知工具与异常兜底
    """

    def __init__(
        self,
        tool_catalog: ToolCatalog,
        timeout_seconds: int | None = None,
        cancellation_context: RunCancellationContext | None = None,
    ):
        self._tool_catalog = tool_catalog
        self._cancellation_context = cancellation_context
        self._timeout_seconds = max(
            1,
            int(timeout_seconds if timeout_seconds is not None else settings.TOOL_EXECUTION_TIMEOUT_SECONDS),
        )

    @staticmethod
    def _resolve_tool_source(message: AIMessage) -> ToolCallSource:
        source = str((message.additional_kwargs or {}).get("tool_call_source") or "").strip().lower()
        return source if source == "hint" else TOOL_CALL_SOURCE_MODEL

    @staticmethod
    def _dedupe_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped_tool_calls: list[dict[str, Any]] = []
        seen_signatures: set[str] = set()

        for tool_call in tool_calls:
            tool_name = str(tool_call.get("name") or "").strip()
            tool_args = _normalize_tool_args(tool_call.get("args"))
            execution_signature = build_tool_execution_signature(tool_name, tool_args)
            if execution_signature in seen_signatures:
                continue
            seen_signatures.add(execution_signature)
            deduped_tool_calls.append(tool_call)

        return deduped_tool_calls

    @staticmethod
    def _extract_tool_calls(message: AIMessage) -> list[dict[str, Any]]:
        return [tool_call for tool_call in message.tool_calls if isinstance(tool_call, dict)]

    def _raise_if_cancelled(self) -> None:
        if self._cancellation_context is not None:
            self._cancellation_context.raise_if_cancelled()

    async def _execute_tool_call(self, tool_call: dict[str, Any], source: ToolCallSource) -> ToolMessage:
        tool_name = str(tool_call.get("name") or "").strip()
        tool_call_id = str(tool_call.get("id") or "").strip()
        tool_args = _normalize_tool_args(tool_call.get("args"))
        tool_args_json = _serialize_tool_args_for_log(tool_args)
        tool = self._tool_catalog.registry_by_name.get(tool_name)

        self._raise_if_cancelled()

        logger.info(
            "[工具调用开始] source=%s tool=%s tool_call_id=%s tool_args=%s timeout_seconds=%d",
            source,
            tool_name,
            tool_call_id,
            tool_args_json,
            self._timeout_seconds,
        )

        if tool is None:
            logger.error(
                "[工具调用失败] source=%s tool=%s tool_call_id=%s tool_args=%s error=tool_not_found",
                source,
                tool_name,
                tool_call_id,
                tool_args_json,
            )
            return _build_error_tool_message(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                source=source,
                error_message=f"tool not found: {tool_name}",
            )

        started_at = perf_counter()
        try:
            tool_result = await await_with_cancellation(
                tool.ainvoke(tool_args),
                cancellation_context=self._cancellation_context,
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int(max(0, (perf_counter() - started_at) * 1000))
            logger.error(
                "[工具调用失败] source=%s tool=%s tool_call_id=%s tool_args=%s status=timeout elapsed_ms=%d",
                source,
                tool_name,
                tool_call_id,
                tool_args_json,
                elapsed_ms,
            )
            return _build_error_tool_message(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                source=source,
                error_message=f"tool execution timed out after {self._timeout_seconds}s",
            )
        except Exception as error:  # noqa: BLE001 - 这里需要把所有工具异常转成 ToolMessage
            elapsed_ms = int(max(0, (perf_counter() - started_at) * 1000))
            logger.exception(
                "[工具调用失败] source=%s tool=%s tool_call_id=%s tool_args=%s status=exception elapsed_ms=%d",
                source,
                tool_name,
                tool_call_id,
                tool_args_json,
                elapsed_ms,
            )
            return _build_error_tool_message(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                source=source,
                error_message=str(error),
            )

        elapsed_ms = int(max(0, (perf_counter() - started_at) * 1000))
        logger.info(
            "[工具调用完成] source=%s tool=%s tool_call_id=%s tool_args=%s status=success elapsed_ms=%d",
            source,
            tool_name,
            tool_call_id,
            tool_args_json,
            elapsed_ms,
        )
        return ToolMessage(
            content=_serialize_tool_output(tool_result),
            tool_call_id=tool_call_id,
            name=tool_name,
            status="success",
            additional_kwargs={"tool_call_source": source},
        )

    async def execute_ai_message(self, message: AIMessage) -> list[ToolMessage]:
        """
        执行一条 AIMessage 上声明的全部 tool_calls。

        说明：
        - 只接受已经明确产出 tool_calls 的 AIMessage；
        - 返回值始终是可直接追加回消息历史的 ToolMessage 列表。
        """

        tool_calls = self._extract_tool_calls(message)
        if not tool_calls:
            return []

        self._raise_if_cancelled()

        source = self._resolve_tool_source(message)
        deduped_tool_calls = self._dedupe_tool_calls(tool_calls)
        removed_count = len(tool_calls) - len(deduped_tool_calls)
        if removed_count > 0:
            logger.debug("[工具执行轮] action=dedupe_duplicate_calls removed_count=%d", removed_count)

        logger.debug(
            "[工具执行轮开始] source=%s tool_count=%d tool_names=%s tool_calls=%s",
            source,
            len(deduped_tool_calls),
            _serialize_tool_names_for_log(deduped_tool_calls),
            _serialize_tool_calls_for_log(deduped_tool_calls),
        )

        started_at = perf_counter()
        tool_messages = []
        for tool_call in deduped_tool_calls:
            self._raise_if_cancelled()
            tool_messages.append(await self._execute_tool_call(tool_call, source))
        elapsed_ms = int(max(0, (perf_counter() - started_at) * 1000))
        logger.debug(
            "[工具执行轮完成] source=%s tool_count=%d tool_names=%s elapsed_ms=%d output_message_count=%d",
            source,
            len(deduped_tool_calls),
            _serialize_tool_names_for_log(deduped_tool_calls),
            elapsed_ms,
            len(tool_messages),
        )
        return tool_messages
