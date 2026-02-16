from __future__ import annotations

import json
from typing import Any, Dict, List


def build_review_guidance_message(
    missing_info: List[str],
    suggested_tool_name: str = "",
    suggested_tool_args: Dict[str, Any] | None = None,
) -> str:
    """
    根据 review 结果构造下一轮模型的内部补证据指令（SystemMessage 内容）。
    """
    missing_lines = "\n".join(f"- {item}" for item in missing_info if str(item).strip())
    normalized_tool_args = suggested_tool_args if isinstance(suggested_tool_args, dict) else {}
    suggested_tool_args_json = json.dumps(normalized_tool_args, ensure_ascii=False)

    guidance_lines = [
        "你上一版回答尚未满足用户问题，请先补齐证据再回答。",
        "若可用工具无法补齐关键证据，请明确告知用户缺失信息并请求补充。",
    ]
    if missing_lines:
        guidance_lines.extend(["当前缺失信息：", missing_lines])
    if suggested_tool_name:
        guidance_lines.append(f"优先尝试工具：{suggested_tool_name}，参数：{suggested_tool_args_json}")
    return "\n".join(guidance_lines)


def build_need_user_input_message(missing_info: List[str], user_guidance: str = "") -> str:
    """
    构造“请用户补充信息”的默认文案；若上游已给出 user_guidance，则优先使用。
    """
    if user_guidance:
        return user_guidance
    missing_text = "；".join(str(item).strip() for item in missing_info if str(item).strip()) or "关键上下文信息"
    return (
        "当前我还无法给出可靠结论。"
        f"缺少：{missing_text}。"
        "请补充这些信息后我再继续分析。"
    )
