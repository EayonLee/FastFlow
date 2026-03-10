from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Iterable, List, Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from nexus.config.config import get_config
from nexus.config.logger import get_logger
from nexus.core.event import is_tool_execution_failed
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)
_settings = get_config()

# 单个用户问题允许执行的工具调用硬上限。
# 这个值不再承担“日常预算”的职责，只是最后一道保险丝，用于防止极端情况下失控循环。
MAX_TOOL_CALLS_PER_QUESTION = max(1, int(_settings.TOOL_MAX_CALLS_PER_QUESTION))

# OpenClaw 风格的循环检测阈值：
# - warning: 只记日志，允许继续尝试
# - critical: 判定当前工具路径已经明显失去进展，停止继续调工具
# - global: 整个问题级别触发熔断，彻底停止本轮工具调用
TOOL_LOOP_WARNING_THRESHOLD = max(1, int(_settings.TOOL_LOOP_WARNING_THRESHOLD))
TOOL_LOOP_CRITICAL_THRESHOLD = max(1, int(_settings.TOOL_LOOP_CRITICAL_THRESHOLD))
TOOL_LOOP_GLOBAL_THRESHOLD = max(1, int(_settings.TOOL_LOOP_GLOBAL_THRESHOLD))

# 循环检测只观察最近一段工具执行历史，避免很早之前的调用污染当前判断。
TOOL_LOOP_HISTORY_SIZE = max(1, int(_settings.TOOL_LOOP_HISTORY_SIZE))

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
    "get_workflow_node_info": ("节点详情", "节点信息", "某个节点", "node", "selected_node", "selected_node("),
    "get_toolset_tools": ("toolset", "工具集合", "工具清单", "mcp"),
    "get_tools_node_mcp_tools": ("tools 节点", "mcp", "挂载", "下挂", "工具"),
    "list_skills": (
        "skill",
        "skills",
        "技能",
        "能力",
        "提示词优化",
        "优化提示词",
        "提示词生成",
        "生成提示词",
        "system prompt",
        "prompt 模板",
        "prompt",
    ),
    "load_skill": (
        "skill",
        "skills",
        "技能",
        "加载技能",
        "提示词优化",
        "优化提示词",
        "提示词生成",
        "生成提示词",
        "system prompt",
        "prompt 模板",
        "prompt",
    ),
    "load_skill_resource": (
        "skill",
        "skills",
        "技能",
        "参考资料",
        "resource",
        "脚本",
        "模板",
        "策略矩阵",
        "安全检查",
    ),
    "get_current_time": ("当前时间", "现在时间", "几点", "日期", "时间", "format", "格式", "时区", "timezone"),
    "get_current_timestamp": ("时间戳", "timestamp", "unix", "毫秒", "秒", "时区", "timezone"),
}


@dataclass(frozen=True)
class ToolExecutionRecord:
    """
    单条工具执行记录。

    execution_signature:
    - 由“工具名 + 参数”组成，用于识别完全相同的重复调用。

    failed:
    - 是否执行失败。这里统一复用 ToolMessage 的失败判定逻辑。
    """

    tool_name: str
    execution_signature: str
    failed: bool


@dataclass(frozen=True)
class ToolLoopCheckResult:
    """
    工具循环检测结果。

    level:
    - none: 未发现明显循环
    - warning: 可疑，但允许继续
    - critical: 当前工具路径已明显陷入循环，停止继续调工具
    - global: 整个问题级别达到熔断阈值
    """

    level: str = "none"
    reason: str = ""
    repeat_count: int = 0


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


def _extract_tool_call_args(raw_call: Any) -> dict[str, Any]:
    """
    将工具调用参数统一解析成 dict。

    说明：
    - LangChain / LiteLLM 不同阶段的 tool_call 结构并不完全一致
    - 这里只保留 dict 形态，非 dict 参数统一视为空对象
    """

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
    """
    生成“工具名 + 参数”的执行签名。

    该签名只用于循环检测与同轮去重，不影响现有“按工具名 no_repeat”策略。
    """

    normalized_name = str(tool_name or "").strip()
    normalized_args = tool_args if isinstance(tool_args, dict) else {}
    normalized_args_json = json.dumps(normalized_args, ensure_ascii=False, sort_keys=True)
    return f"{normalized_name}::{normalized_args_json}"


def iter_tool_calls(messages: Sequence[BaseMessage]) -> Iterable[str]:
    """
    迭代消息里的全部工具调用。
    """

    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for raw_call in message.tool_calls or []:
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

    说明：
    - 该计数只用于全局安全保险丝，不再作为日常的“小预算”使用。
    """

    return sum(1 for message in messages if isinstance(message, ToolMessage))


def _iter_recent_tool_execution_records(messages: Sequence[BaseMessage]) -> List[ToolExecutionRecord]:
    """
    将消息流还原成最近一段工具执行记录。

    还原规则：
    - AIMessage.tool_calls 视为“工具调用请求”
    - 后续 ToolMessage 视为“工具执行结果”
    - 两者按消息顺序配对，得到“工具名 + 参数 + 成败”的执行记录
    """

    pending_calls: Deque[tuple[str, str]] = deque()
    execution_records: List[ToolExecutionRecord] = []

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
    """
    统计最近连续多少次都在执行同一组“工具名 + 参数”。
    """

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
    """
    统计最近连续多少次都在执行同一组“工具名 + 参数”，且全部失败。
    """

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
    """
    统计最近的“乒乓式”工具循环长度。

    判定方式：
    - 只看工具名，不看参数
    - 最近序列必须只涉及两个工具名
    - 后缀形如 A -> B -> A -> B ...
    """

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
    """
    根据重复次数映射告警等级。
    """

    if repeat_count >= TOOL_LOOP_GLOBAL_THRESHOLD:
        return ToolLoopCheckResult(level="global", reason=reason, repeat_count=repeat_count)
    if repeat_count >= TOOL_LOOP_CRITICAL_THRESHOLD:
        return ToolLoopCheckResult(level="critical", reason=reason, repeat_count=repeat_count)
    if repeat_count >= TOOL_LOOP_WARNING_THRESHOLD:
        return ToolLoopCheckResult(level="warning", reason=reason, repeat_count=repeat_count)
    return ToolLoopCheckResult()


def detect_tool_loop(messages: Sequence[BaseMessage]) -> ToolLoopCheckResult:
    """
    用轻量方式检测工具循环。

    参考 OpenClaw 的设计思路，这里不再使用“连续几次没有新增证据就停”的硬编码规则，
    而是只关注真正的无进展模式：
    1) generic_repeat: 同一工具 + 相同参数被重复执行
    2) repeated_failure: 同一工具 + 相同参数连续失败
    3) ping_pong: 两个工具反复来回切换
    """

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

    focus_text:
    - 额外关注文本，例如 review 节点产出的 missing_info
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
    1) 全局安全保险丝：单个问题最多 50 次工具结果，超过后直接停止。
    2) OpenClaw 风格 loop detection：对“重复无进展模式”做 warning / critical / global 分级。
    3) no_repeat：同名工具重复由执行层拦截，策略层不全局停机。

    基础规则：
    4) 已有 ToolMessage 时使用 auto。
    5) 首轮且问题依赖工作流图时使用 required。
    6) 其他场景使用 auto。
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

    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
    if has_tool_result:
        logger.info("[工具选择策略] 动作=模型自主决策 结果=auto（已有工具结果）")
        return "auto"

    if requires_workflow_graph_tools(context.user_prompt):
        logger.info("[工具选择策略] 强制先调工具 结果=required")
        return "required"

    logger.info("[工具选择策略] 模型自主决策 结果=auto")
    return "auto"
