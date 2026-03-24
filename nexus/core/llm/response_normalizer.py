from __future__ import annotations

"""
模型返回内容标准化中心。

该模块负责处理多模型“思考内容载体差异”，并输出统一结果：
1) 面向用户回答：提取 answer_text + reasoning_text

兼容重点（当前模型池）：
- MiniMax M2.5：`<think>...</think>` / `reasoning_details`
- Qwen3.5：`reasoning_content`
- Kimi K2.5：`reasoning_content`
- GLM-5：`reasoning_content`
"""

import re
from typing import Any, Iterable, Mapping, Tuple

THINK_TAG_NAMES = ("think", "thinking", "reasoning", "analysis")
THINK_BLOCK_PATTERNS = tuple(
    re.compile(rf"<{tag}>([\s\S]*?)</{tag}>", flags=re.IGNORECASE) for tag in THINK_TAG_NAMES
)
THINK_SINGLE_TAG_PATTERN = re.compile(r"</?(?:" + "|".join(THINK_TAG_NAMES) + r")>", flags=re.IGNORECASE)
THINK_OPEN_TAGS = tuple(f"<{tag}>".lower() for tag in THINK_TAG_NAMES)
THINK_CLOSE_TAGS = tuple(f"</{tag}>".lower() for tag in THINK_TAG_NAMES)
THINK_STREAM_TAGS = THINK_OPEN_TAGS + THINK_CLOSE_TAGS


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _content_to_text(content: Any) -> str:
    """
    将多形态 content 归一化为文本。
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                for key in ("text", "content", "reasoning_content"):
                    value = item.get(key)
                    if value is None:
                        continue
                    chunks.append(str(value))
                    break
                continue
            chunks.append(str(item))
        return "".join(chunks)
    return str(content)


def _is_model_family(model_id: str, families: Iterable[str]) -> bool:
    normalized = _normalize_text(model_id).lower()
    if not normalized:
        return False
    return any(family in normalized for family in families)


def _collect_reasoning_from_additional_kwargs(
    additional_kwargs: Mapping[str, Any] | None,
    *,
    model_id: str,
) -> list[str]:
    """
    从 additional_kwargs 抽取各 provider 常见的思考字段。
    """
    payload = dict(additional_kwargs or {})
    collected: list[str] = []

    for key in ("reasoning_content", "reasoning", "thinking"):
        value = _normalize_text(payload.get(key))
        if value:
            collected.append(value)

    reasoning_details = payload.get("reasoning_details")
    if isinstance(reasoning_details, list):
        for item in reasoning_details:
            if isinstance(item, dict):
                detail_text = _normalize_text(item.get("text") or item.get("content") or item.get("reasoning_content"))
                if detail_text:
                    collected.append(detail_text)
            else:
                detail_text = _normalize_text(item)
                if detail_text:
                    collected.append(detail_text)

    # MiniMax 兼容：部分响应会把思考字段放在 provider 自定义键里。
    if _is_model_family(model_id, ("minimax",)):
        for key in ("reasoning_text", "reasoningSummary"):
            value = _normalize_text(payload.get(key))
            if value:
                collected.append(value)

    # Qwen/Kimi/GLM 兼容：主要载体是 reasoning_content，以下键用于兜住兼容格式差异。
    if _is_model_family(model_id, ("qwen", "kimi", "moonshot", "glm")):
        for key in ("thinking_content",):
            value = _normalize_text(payload.get(key))
            if value:
                collected.append(value)

    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in collected:
        if item in seen:
            continue
        seen.add(item)
        deduplicated.append(item)
    return deduplicated


def _find_first_tag(text: str, tags: tuple[str, ...]) -> tuple[int, str]:
    lowered = text.lower()
    matched_index = -1
    matched_tag = ""

    for tag in tags:
        index = lowered.find(tag)
        if index < 0:
            continue
        if matched_index < 0 or index < matched_index or (index == matched_index and len(tag) > len(matched_tag)):
            matched_index = index
            matched_tag = tag

    return matched_index, matched_tag


def _resolve_partial_tag_prefix_length(text: str) -> int:
    lowered = text.lower()
    longest_prefix = 0

    for tag in THINK_STREAM_TAGS:
        max_prefix_length = min(len(lowered), len(tag) - 1)
        for prefix_length in range(max_prefix_length, 0, -1):
            if lowered.endswith(tag[:prefix_length]):
                longest_prefix = max(longest_prefix, prefix_length)
                break

    return longest_prefix


class InlineThinkingStreamParser:
    """
    解析流式正文中的 `<think>...</think>` 片段。

    部分 provider 会把思考内容直接混在 content 流里返回。
    这里在增量阶段就把“思考”和“最终回答”拆开，避免先把 `<think>` 内容流到聊天气泡，
    之后再通过 `answer.reset` 回滚。
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_thinking = False
        self._answer_started = False
        self._reasoning_started = False

    def feed(self, text: str) -> tuple[str, str]:
        if text:
            self._buffer = f"{self._buffer}{text}"
        return self._drain(final=False)

    def flush(self) -> tuple[str, str]:
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> tuple[str, str]:
        answer_parts: list[str] = []
        reasoning_parts: list[str] = []

        while self._buffer:
            if self._inside_thinking:
                close_index, close_tag = _find_first_tag(self._buffer, THINK_CLOSE_TAGS)
                if close_index >= 0:
                    if close_index > 0:
                        self._append_reasoning_chunk(
                            reasoning_parts,
                            self._buffer[:close_index],
                            final_chunk=True,
                        )
                    self._buffer = self._buffer[close_index + len(close_tag) :]
                    self._inside_thinking = False
                    continue

                safe_text = self._consume_safe_text(final=final)
                if safe_text:
                    self._append_reasoning_chunk(reasoning_parts, safe_text, final_chunk=final)
                break

            open_index, open_tag = _find_first_tag(self._buffer, THINK_OPEN_TAGS)
            if open_index >= 0:
                if open_index > 0:
                    self._append_answer_chunk(
                        answer_parts,
                        self._buffer[:open_index],
                        final_chunk=True,
                    )
                self._buffer = self._buffer[open_index + len(open_tag) :]
                self._inside_thinking = True
                continue

            safe_text = self._consume_safe_text(final=final)
            if safe_text:
                self._append_answer_chunk(answer_parts, safe_text, final_chunk=final)
            break

        return "".join(answer_parts), "".join(reasoning_parts)

    def _consume_safe_text(self, *, final: bool) -> str:
        if not self._buffer:
            return ""
        if final:
            safe_text = self._buffer
            self._buffer = ""
            return safe_text

        holdback_length = _resolve_partial_tag_prefix_length(self._buffer)
        if holdback_length <= 0:
            safe_text = self._buffer
            self._buffer = ""
            return safe_text
        if holdback_length >= len(self._buffer):
            return ""

        safe_text = self._buffer[:-holdback_length]
        self._buffer = self._buffer[-holdback_length:]
        return safe_text

    def _append_answer_chunk(self, parts: list[str], text: str, *, final_chunk: bool) -> None:
        normalized = self._normalize_visible_chunk(
            text,
            started=self._answer_started,
            final_chunk=final_chunk,
        )
        if not normalized:
            return
        self._answer_started = True
        parts.append(normalized)

    def _append_reasoning_chunk(self, parts: list[str], text: str, *, final_chunk: bool) -> None:
        normalized = self._normalize_visible_chunk(
            text,
            started=self._reasoning_started,
            final_chunk=final_chunk,
        )
        if not normalized:
            return
        self._reasoning_started = True
        parts.append(normalized)

    @staticmethod
    def _normalize_visible_chunk(text: str, *, started: bool, final_chunk: bool) -> str:
        normalized = text
        if not started:
            normalized = normalized.lstrip()
        if final_chunk:
            normalized = normalized.rstrip()
        return normalized


def _split_think_wrapped_content(content: Any) -> Tuple[str, str, bool]:
    """
    从文本中分离“回答正文”和“思考文本”。

    兼容：
    - 成对标签：`<think>...</think>`
    - 仅闭合标签：`... </think> ...`
    - 仅起始标签：`... <think> ...`
    """
    text = _content_to_text(content)
    if not text:
        return "", "", False

    reasoning_parts: list[str] = []
    answer = text
    had_reasoning = False

    for pattern in THINK_BLOCK_PATTERNS:
        matches = [segment.strip() for segment in pattern.findall(answer) if segment and segment.strip()]
        if matches:
            had_reasoning = True
            reasoning_parts.extend(matches)
            answer = pattern.sub("\n", answer)

    lower_text = text.lower()
    if not reasoning_parts and "</think>" in lower_text and "<think>" not in lower_text:
        split_index = lower_text.find("</think>")
        maybe_reasoning = text[:split_index].strip()
        maybe_answer = text[split_index + len("</think>") :].strip()
        if maybe_reasoning:
            reasoning_parts.append(maybe_reasoning)
            answer = maybe_answer
            had_reasoning = True
    elif not reasoning_parts and "<think>" in lower_text and "</think>" not in lower_text:
        split_index = lower_text.find("<think>")
        maybe_answer = text[:split_index].strip()
        maybe_reasoning = text[split_index + len("<think>") :].strip()
        if maybe_reasoning:
            reasoning_parts.append(maybe_reasoning)
            answer = maybe_answer
            had_reasoning = True

    answer = THINK_SINGLE_TAG_PATTERN.sub("", answer).strip()
    reasoning = "\n".join([part for part in reasoning_parts if part]).strip()
    return answer, reasoning, had_reasoning


def normalize_answer_and_reasoning(
    content: Any,
    additional_kwargs: Mapping[str, Any] | None = None,
    *,
    model_id: str = "",
) -> tuple[str, str]:
    """
    标准化模型输出：
    - answer_text: 面向用户的回答正文
    - reasoning_text: 可选思考内容（供前端“思考过程”展示）
    """
    answer_text, tag_reasoning, _ = _split_think_wrapped_content(content)
    kwargs_reasoning = _collect_reasoning_from_additional_kwargs(additional_kwargs, model_id=model_id)

    merged_reasoning_parts: list[str] = []
    if tag_reasoning:
        merged_reasoning_parts.append(tag_reasoning)
    merged_reasoning_parts.extend(kwargs_reasoning)
    merged_reasoning = "\n".join([part for part in merged_reasoning_parts if part]).strip()
    return answer_text, merged_reasoning
