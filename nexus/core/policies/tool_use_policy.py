from typing import Sequence

from langchain_core.messages import BaseMessage, ToolMessage

from nexus.core.schemas import ChatRequestContext

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

def requires_workflow_graph_tools(user_prompt: str) -> bool:
    """
    判断用户问题是否显式依赖当前工作流图上下文。
    """
    prompt = (user_prompt or "").strip().lower()
    if not prompt:
        return False
    return any(keyword in prompt for keyword in WORKFLOW_GRAPH_CONTEXT_KEYWORDS)


def resolve_tool_choice(context: ChatRequestContext, messages: Sequence[BaseMessage]) -> str:
    """
    统一计算本轮模型调用的 tool_choice 策略。

    规则：
    1) 若已经存在 ToolMessage，说明已进入工具往返阶段，使用 auto。
    2) 若首轮问题显式依赖工作流图，使用 required 强制至少一次工具调用。
    3) 其他场景使用 auto。
    """
    has_tool_result = any(isinstance(message, ToolMessage) for message in messages)
    if has_tool_result:
        return "auto"
    if requires_workflow_graph_tools(context.user_prompt):
        return "required"
    return "auto"
