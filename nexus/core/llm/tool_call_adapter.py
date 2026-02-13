import json
from json import JSONDecodeError
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.tool import tool_call
from nexus.config.logger import get_logger

logger = get_logger(__name__)


class ToolCallIdAdapter:
    """
    LLM 适配层：为缺失 tool_call_id 的工具调用补齐 ID。
    """

    def __init__(self, model: Any):
        self._model = model

    def bind_tools(self, tools: list | None, **kwargs):
        return ToolCallIdAdapter(self._model.bind_tools(tools, **kwargs)) if tools else self

    def invoke(self, *args, **kwargs):
        result = self._model.invoke(*args, **kwargs)
        return ensure_tool_call_ids(result)

    async def ainvoke(self, *args, **kwargs):
        result = await self._model.ainvoke(*args, **kwargs)
        return ensure_tool_call_ids(result)

    def __getattr__(self, name: str):
        return getattr(self._model, name)


def _normalize_tool_call_object(raw_call: Any) -> dict[str, Any]:
    """
    将不同来源的 tool_call 对象统一为 dict 结构。
    """
    if isinstance(raw_call, dict):
        return raw_call
    if hasattr(raw_call, "model_dump"):
        return raw_call.model_dump()
    if hasattr(raw_call, "__dict__"):
        return dict(raw_call.__dict__)
    return {
        "id": getattr(raw_call, "id", None),
        "name": getattr(raw_call, "name", None),
        "args": getattr(raw_call, "args", None),
    }


def _parse_call_arguments(arguments_raw: Any) -> dict[str, Any]:
    """
    将 tool_call 参数解析为 dict。
    """
    if isinstance(arguments_raw, dict):
        return arguments_raw
    if isinstance(arguments_raw, str):
        try:
            parsed = json.loads(arguments_raw)
            return parsed if isinstance(parsed, dict) else {}
        except JSONDecodeError:
            return {}
    return {}


def _build_normalized_tool_call(call_data: dict[str, Any], message_id: str | None) -> tuple[Any | None, bool]:
    """
    归一化单条 tool_call，返回 (tool_call对象, 是否补过ID)。
    """
    call_id = call_data.get("id")
    id_patched = not str(call_id or "").strip()
    if id_patched:
        call_id = f"call_{uuid4().hex}"

    function_data = call_data.get("function")
    if isinstance(function_data, dict):
        call_name = function_data.get("name")
        call_args = _parse_call_arguments(function_data.get("arguments"))
    else:
        call_name = call_data.get("name")
        call_args = _parse_call_arguments(call_data.get("args"))

    if not call_name:
        logger.warning("Skip malformed tool_call without name. message_id=%s", message_id)
        return None, id_patched

    return tool_call(name=call_name, args=call_args, id=str(call_id)), id_patched


def ensure_tool_call_ids(message: BaseMessage) -> BaseMessage:
    """
    确保 tool_calls 中的每个调用都有 id，避免 tool_call_id not found 错误。
    """
    if not isinstance(message, AIMessage):
        return message
    raw_tool_calls = message.tool_calls or (message.additional_kwargs or {}).get("tool_calls")
    if not raw_tool_calls:
        logger.warning("Tool call missing in AIMessage. message_id=%s", message.id)
        return message

    normalized_calls = []
    missing_id_count = 0
    for raw_call in raw_tool_calls:
        call_data = _normalize_tool_call_object(raw_call)
        normalized_call, id_patched = _build_normalized_tool_call(call_data, message.id)
        if id_patched:
            missing_id_count += 1
        if normalized_call is not None:
            normalized_calls.append(normalized_call)

    if missing_id_count > 0:
        logger.warning("Patched tool_call id count=%s message_id=%s", missing_id_count, message.id)

    if not normalized_calls:
        return message

    updated_kwargs = dict(message.additional_kwargs or {})
    updated_kwargs["tool_calls"] = [
        {
            "id": call["id"],
            "type": "function",
            "function": {"name": call["name"], "arguments": json.dumps(call["args"], ensure_ascii=False)},
        }
        for call in normalized_calls
    ]

    return AIMessage(
        content=message.content,
        additional_kwargs=updated_kwargs,
        response_metadata=message.response_metadata,
        tool_calls=normalized_calls,
        id=message.id,
    )
