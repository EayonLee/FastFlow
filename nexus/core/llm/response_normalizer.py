from __future__ import annotations

"""
模型返回内容标准化中心。

该模块负责处理多模型“思考内容载体差异”，并输出统一结果：
1) 面向用户回答：提取 answer_text + reasoning_text
2) 面向结构化控制面：去除思考包裹后提取 JSON

兼容重点（当前模型池）：
- MiniMax M2.5：`<think>...</think>` / `reasoning_details`
- Qwen3.5：`reasoning_content`
- Kimi K2.5：`reasoning_content`
- GLM-5：`reasoning_content`
"""

import json
import re
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Iterable, Mapping, Tuple

THINK_TAG_NAMES = ("think", "thinking", "reasoning", "analysis")
THINK_BLOCK_PATTERNS = tuple(
    re.compile(rf"<{tag}>([\s\S]*?)</{tag}>", flags=re.IGNORECASE) for tag in THINK_TAG_NAMES
)
THINK_SINGLE_TAG_PATTERN = re.compile(r"</?(?:" + "|".join(THINK_TAG_NAMES) + r")>", flags=re.IGNORECASE)
JSON_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", flags=re.IGNORECASE)


@dataclass(frozen=True)
class StructuredJsonNormalizationResult:
    """
    结构化输出标准化结果。
    """

    payload: dict[str, Any]
    had_reasoning: bool
    source: str


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


def _parse_json_from_text(text: str) -> tuple[dict[str, Any], str]:
    stripped = _normalize_text(text)
    if not stripped:
        raise ValueError("empty structured output")

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed, "full_text"
    except JSONDecodeError:
        pass

    for match in JSON_CODE_BLOCK_PATTERN.finditer(stripped):
        candidate = _normalize_text(match.group(1))
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed, "json_code_block"
        except JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[index:])
            if isinstance(parsed, dict):
                return parsed, "json_fragment"
        except JSONDecodeError:
            continue

    raise ValueError("structured output does not contain a valid json object")


def normalize_structured_json(
    content: Any,
    additional_kwargs: Mapping[str, Any] | None = None,
    *,
    model_id: str = "",
) -> StructuredJsonNormalizationResult:
    """
    标准化结构化输出：
    1) 去除思考内容（标签/kwargs）
    2) 提取首个合法 JSON 对象
    """
    answer_text, reasoning_text = normalize_answer_and_reasoning(
        content,
        additional_kwargs,
        model_id=model_id,
    )
    payload, source = _parse_json_from_text(answer_text if answer_text else _content_to_text(content))
    return StructuredJsonNormalizationResult(
        payload=payload,
        had_reasoning=bool(_normalize_text(reasoning_text)),
        source=source,
    )
