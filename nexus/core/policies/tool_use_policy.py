from __future__ import annotations

import json
from typing import Any, Iterable, List, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from nexus.config.logger import get_logger
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)

# 每个用户问题最多允许执行的工具调用次数（tool budget）。
# 该值仅约束 ToolMessage 产生次数，不约束回答充足性复核轮次。
MAX_TOOL_CALLS_PER_QUESTION = 3
# 连续 N 次没有新增证据时，停止继续调工具。
NO_NEW_EVIDENCE_STOP_STREAK = 2

# 包含 WORKFLOW_GRAPH_CONTEXT_KEYWORDS
# 会触发 tool_choice="required"（首轮强制至少调用一次工具）。
# 不包含关键词
# 走 tool_choice="auto"，模型仍然可能调用工具，只是不强制。
WORKFLOW_GRAPH_CONTEXT_KEYWORDS = (
    "当前工作流",
    "这个工作流",
    "流程图",
    "编排图",
    "节点",
    "连线",
    "边",
    "拓扑",
    "node",
    "nodes",
    "edge",
    "edges",
    "workflow",
    "graph",
    # MCP 工具 / toolSet / tools 节点相关问题通常依赖当前工作流图上下文。
    "mcp",
    "mcp工具",
    "mcp 工具",
    "toolset",
)

# 工具关键词映射：用于粗粒度相关性打分（不做问题意图分类）。
TOOL_KEYWORDS = {
    "get_workflow_meta": ("名称", "描述", "简介", "用途", "干啥", "做什么"),
    "get_full_workflow_graph": ("完整", "全量", "全部", "流程", "连线", "拓扑", "上下游"),
    "find_workflow_graph_nodes": ("查找", "搜索", "定位", "节点"),
    "get_workflow_node_info": ("节点详情", "节点信息", "某个节点", "node"),
    "get_toolset_tools": ("toolset", "工具集合", "工具清单", "mcp"),
    "get_tools_node_mcp_tools": ("tools 节点", "mcp", "挂载", "下挂", "工具"),
    "get_current_time": ("当前时间", "现在时间", "几点", "日期", "时间", "format", "格式", "时区", "timezone"),
    "get_current_timestamp": ("时间戳", "timestamp", "unix", "毫秒", "秒", "时区", "timezone"),
}

def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def build_tool_call_signature(tool_name: str) -> str:
    """
    生成工具调用签名（按工具名去重）。
    """
    return str(tool_name or "").strip()


def _extract_tool_call_name(raw_call: Any) -> str:
    if isinstance(raw_call, dict):
        return str(raw_call.get("name") or "").strip()
    return str(getattr(raw_call, "name", "") or "").strip()


def iter_tool_calls(messages: Sequence[BaseMessage]) -> Iterable[str]:
    """
    迭代消息里的全部工具调用。
    """
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for raw_call in (message.tool_calls or []):
            tool_name = _extract_tool_call_name(raw_call)
            if tool_name:
                yield tool_name


def collect_tool_call_signatures(messages: Sequence[BaseMessage]) -> List[str]:
    """
    收集工具调用签名（按时间顺序）。
    """
    return [build_tool_call_signature(tool_name) for tool_name in iter_tool_calls(messages)]


def get_tool_message_count(messages: Sequence[BaseMessage]) -> int:
    """
    统计当前轮次累计产生的 ToolMessage 数量。
    """
    return sum(1 for message in messages if isinstance(message, ToolMessage))


def _normalize_tool_result_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: List[str] = []
        for item in content:
            if isinstance(item, dict):
                chunks.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
            else:
                chunks.append(str(item))
        return "\n".join(chunks).strip()
    return str(content or "").strip()


def _no_new_evidence_streak(messages: Sequence[BaseMessage]) -> int:
    """
    计算“连续无新增证据”次数。

    判定规则：
    - ToolMessage 内容为空，记为无新增证据
    - ToolMessage 内容与历史完全一致，记为无新增证据
    - 其余视为新增证据，并重置连续计数
    """
    seen_evidence = set()
    streak = 0
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        normalized_content = _normalize_tool_result_content(message.content)
        if not normalized_content or normalized_content in seen_evidence:
            streak += 1
            continue
        seen_evidence.add(normalized_content)
        streak = 0
    return streak


def requires_workflow_graph_tools(user_prompt: str) -> bool:
    """
    判断用户问题是否显式依赖当前工作流图上下文。
    """
    prompt = _normalize_text(user_prompt)
    if not prompt:
        return False
    return any(keyword in prompt for keyword in WORKFLOW_GRAPH_CONTEXT_KEYWORDS)


def _score_tool_relevance(tool: Any, query_text: str) -> int:
    """
    对工具进行粗粒度相关性打分。
    """
    if not query_text:
        return 0

    tool_name = str(getattr(tool, "name", "") or "")
    tool_description = _normalize_text(getattr(tool, "description", ""))
    score = 0

    if tool_name and tool_name.lower() in query_text:
        score += 10

    for keyword in TOOL_KEYWORDS.get(tool_name, ()):
        if _normalize_text(keyword) in query_text:
            score += 3

    for fallback_token in ("工作流", "节点", "工具", "mcp", "描述", "名称", "连线"):
        normalized_token = _normalize_text(fallback_token)
        if normalized_token in query_text and normalized_token in tool_description:
            score += 1

    return score


def select_tool_candidates(
    context: ChatRequestContext,
    messages: Sequence[BaseMessage],
    tools: Sequence[Any],
    focus_text: str = "",
) -> List[Any]:
    """
    对工具做相关性排序，并过滤已执行过的同名工具。

    focus_text：额外关注文本（例如 review 节点输出的 missing_info）。
    """
    if not tools:
        return []

    query_text = _normalize_text(f"{context.user_prompt or ''} {focus_text or ''}")
    scored_tools = [(_score_tool_relevance(tool, query_text), index, tool) for index, tool in enumerate(tools)]
    scored_tools.sort(key=lambda item: (-item[0], item[1]))

    candidate_tools = [item[2] for item in scored_tools]

    # no_repeat（按工具名）：已执行过的工具从候选集中移除。
    called_signatures = set(collect_tool_call_signatures(messages))
    filtered_tools: List[Any] = []
    for tool in candidate_tools:
        tool_name = str(getattr(tool, "name", "") or "")
        signature = build_tool_call_signature(tool_name)
        if signature in called_signatures:
            continue
        filtered_tools.append(tool)

    return filtered_tools or candidate_tools


def resolve_tool_choice(context: ChatRequestContext, messages: Sequence[BaseMessage]) -> str:
    """
    统一计算本轮模型调用的 tool_choice 策略。

    约束规则：
    1) tool_budget：每个问题最多 3 次工具调用，超限后返回 none。
    2) no_repeat：同名工具重复由执行层拦截，策略层不全局停机。
    3) no_new_evidence_stop：连续 2 次无新增证据后，停止继续调工具（返回 none）。

    基础规则：
    4) 已有 ToolMessage 时使用 auto。
    5) 首轮且问题依赖工作流图时使用 required。
    6) 其他场景使用 auto。
    """
    tool_message_count = get_tool_message_count(messages)
    if tool_message_count >= MAX_TOOL_CALLS_PER_QUESTION:
        logger.info(
            "[工具选择策略] 动作=停止调工具 原因=达到预算上限(%d/%d)",
            tool_message_count,
            MAX_TOOL_CALLS_PER_QUESTION,
        )
        return "none"

    no_new_evidence_streak = _no_new_evidence_streak(messages)
    if no_new_evidence_streak >= NO_NEW_EVIDENCE_STOP_STREAK:
        logger.info(
            "[工具选择策略] 动作=停止调工具 原因=连续无新增证据(%d/%d)",
            no_new_evidence_streak,
            NO_NEW_EVIDENCE_STOP_STREAK,
        )
        return "none"

    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
    if has_tool_result:
        logger.info(
            "[工具选择策略] 动作=模型自主决策 结果=auto（已有工具结果）",
        )
        return "auto"

    if requires_workflow_graph_tools(context.user_prompt):
        logger.info(
            "[工具选择策略] 强制先调工具 结果=required",
        )
        return "required"

    logger.info(
        "[工具选择策略] 模型自主决策 结果=auto",
    )
    return "auto"
