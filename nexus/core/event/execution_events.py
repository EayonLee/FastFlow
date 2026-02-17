from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Dict, List

from langchain_core.messages import ToolMessage

PHASE_ANALYZE_QUESTION = "analyze_question"
PHASE_EXECUTE_TOOLS = "execute_tools"
PHASE_REVIEW_ANSWER = "review_answer"
PHASE_GENERATE_FINAL_ANSWER = "generate_final_answer"


def build_run_started_event(*, agent: str) -> Dict[str, Any]:
    return {
        "type": "run.started",
        "message": "开始处理用户问题",
        "agent": agent,
    }


def build_run_completed_event(*, final_answer_len: int) -> Dict[str, Any]:
    return {
        "type": "run.completed",
        "message": "本轮处理完成",
        "final_answer_len": final_answer_len,
    }


def build_answer_delta_event(delta: str) -> Dict[str, Any]:
    return {
        "type": "answer.delta",
        "content": delta,
    }


def build_answer_done_event(content: str) -> Dict[str, Any]:
    return {
        "type": "answer.done",
        "content": content,
    }


def build_thinking_delta_event(content: str) -> Dict[str, Any]:
    return {
        "type": "thinking.delta",
        "content": content,
    }


def build_thinking_summary_event(content: str) -> Dict[str, Any]:
    return {
        "type": "thinking.summary",
        "content": content,
    }


class PhaseTracker:
    """维护阶段状态并生成 started/completed 事件。"""

    def __init__(self, initial_phase: str, initial_message: str):
        self.current_phase = initial_phase
        self.initial_message = initial_message

    def build_start_events(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "phase.started",
                "phase": self.current_phase,
                "message": self.initial_message,
            }
        ]

    def transition_to(self, next_phase: str, start_message: str) -> List[Dict[str, Any]]:
        if next_phase == self.current_phase:
            return []
        previous_phase = self.current_phase
        self.current_phase = next_phase
        return [
            {
                "type": "phase.completed",
                "phase": previous_phase,
                "message": f"阶段完成：{previous_phase}",
            },
            {
                "type": "phase.started",
                "phase": self.current_phase,
                "message": start_message,
            },
        ]

    def build_completed_event(self) -> Dict[str, Any]:
        return {
            "type": "phase.completed",
            "phase": self.current_phase,
            "message": f"阶段完成：{self.current_phase}",
        }


def extract_text_from_stream_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or item.get("content") or "").strip()
            if text:
                parts.append(text)
        return "".join(parts)
    return str(content or "")


def extract_reasoning_from_stream_chunk(chunk: Any) -> str:
    def _extract_from_payload(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        for key in ("reasoning_content", "reasoning", "thinking"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                parts: List[str] = []
                for item in value:
                    if isinstance(item, str) and item.strip():
                        parts.append(item)
                        continue
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or item.get("content") or "").strip()
                    if text:
                        parts.append(text)
                if parts:
                    return "".join(parts)
        return ""

    additional_reasoning = _extract_from_payload(getattr(chunk, "additional_kwargs", {}) or {})
    if additional_reasoning:
        return additional_reasoning

    metadata_reasoning = _extract_from_payload(getattr(chunk, "response_metadata", {}) or {})
    if metadata_reasoning:
        return metadata_reasoning

    content = getattr(chunk, "content", "")
    if not isinstance(content, list):
        return ""
    parts: List[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type not in {"reasoning", "thinking"}:
            continue
        text = str(item.get("text") or item.get("content") or "").strip()
        if text:
            parts.append(text)
    return "".join(parts)


def _resolve_tool_call_key_from_call(tool_call: Dict[str, Any]) -> str:
    tool_call_id = str(tool_call.get("id") or "").strip()
    if tool_call_id:
        return tool_call_id
    return str(tool_call.get("name") or "").strip()


def _resolve_tool_call_key_from_message(message: ToolMessage) -> str:
    tool_call_id = str(getattr(message, "tool_call_id", "") or "").strip()
    if tool_call_id:
        return tool_call_id
    return str(getattr(message, "name", "") or "").strip()


def is_tool_execution_failed(tool_message: ToolMessage) -> bool:
    status = str(getattr(tool_message, "status", "") or "").strip().lower()
    if status in {"error", "failed", "fail"}:
        return True
    content = str(tool_message.content or "").strip()
    if not content:
        return False
    lowered = content.lower()
    if lowered.startswith("error:") or "traceback" in lowered:
        return True
    try:
        data = json.loads(content)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("error"):
        return True
    json_status = str(data.get("status") or "").strip().lower()
    return json_status in {"error", "failed", "fail"}


class ToolExecutionTracker:
    """按 tool_call_id 记录开始时刻并计算耗时。"""

    def __init__(self):
        self._started_at: Dict[str, float] = {}

    def mark_started(self, tool_call: Dict[str, Any]) -> None:
        key = _resolve_tool_call_key_from_call(tool_call)
        if key:
            self._started_at[key] = perf_counter()

    def pop_elapsed_ms(self, tool_message: ToolMessage) -> int | None:
        key = _resolve_tool_call_key_from_message(tool_message)
        if not key or key not in self._started_at:
            return None
        elapsed_ms = int(max(0, (perf_counter() - self._started_at.pop(key)) * 1000))
        return elapsed_ms
