from typing import Annotated, AsyncGenerator, List, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.llm import get_or_create_chat_model
from nexus.core.memory.memory_manager import get_session_history
from nexus.core.prompts.chat_prompts import CHAT_SYSTEM_PROMPT
from nexus.core.schemas import ChatRequestContext
from nexus.core.tools import build_workflow_graph_tools

logger = get_logger(__name__)

class ChatState(TypedDict):
    # LangGraph 中的状态：messages 是增量追加的消息列表。
    messages: Annotated[List[BaseMessage], "add_messages"]


class ChatAgent:
    """
    通用对话 Agent（支持按需调用工具）。

    主要职责：
    1) 组装系统提示词与历史消息
    2) 按配置构建可执行的 LangGraph
    3) 处理流式对话请求并写入历史
    """

    def __init__(self):
        pass

    def _build_init_messages(self, context: ChatRequestContext) -> List[BaseMessage]:
        # 读取当前会话历史（按 session_id 隔离）。
        history = get_session_history(context.session_id)
        # 消息顺序：系统提示词 -> 历史消息 -> 本轮用户输入。
        return [
            SystemMessage(content=CHAT_SYSTEM_PROMPT),
            *history.messages,
            HumanMessage(content=context.user_prompt),
        ]

    def _build_app(self, context: ChatRequestContext):
        # 从上下文读取模型配置 ID。
        config_id = context.model_config_id
        if not config_id:
            raise BusinessError("缺少模型配置 ID (model_config_id)")

        # 获取工作流工具
        tools, _ = build_workflow_graph_tools(context)
        # 构建/复用 LLM，注入工具与鉴权信息。
        llm = get_or_create_chat_model(config_id, context.auth_token, tools)

        def agent_node(state: ChatState):
            # 取出当前消息列表，调用模型生成响应。
            messages = state["messages"]
            response = llm.invoke(messages)
            # 返回增量消息
            return {"messages": [response]}

        def router(state: ChatState) -> Literal["tools", "__end__"]:
            # 根据最后一条消息判断是否需要触发工具调用。
            last_message = state["messages"][-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return "__end__"

        # 构建对话工作流：agent -> (tools?) -> agent -> ...
        workflow = StateGraph(ChatState)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", ToolNode(tools))
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges("agent", router, {"tools": "tools", "__end__": END})
        workflow.add_edge("tools", "agent")
        # 编译为可执行图实例。
        return workflow.compile()

    async def achat(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理流式对话请求。
        """
        # 构建当前会话的 LangGraph 执行图（包含工具路由）。
        app = self._build_app(context)
        # 初始化状态：系统提示词 + 历史记录 + 本轮用户输入。
        state: ChatState = {"messages": self._build_init_messages(context)}
        # 用于拼接流式输出的完整答案。
        answer_parts: List[str] = []
        # 记录上一条已输出的完整内容，用于计算增量。
        last_emitted = ""

        # 使用 values 流模式：每次输出当前状态快照（包含 messages 列表）。
        async for update in app.astream(state, stream_mode="values"):
            if not isinstance(update, dict):
                continue
            messages = update.get("messages")
            if not isinstance(messages, list) or not messages:
                continue
            last_message = messages[-1]
            if not isinstance(last_message, AIMessage):
                continue
            content = last_message.content or ""
            if not content:
                continue
            if last_emitted and content.startswith(last_emitted):
                delta = content[len(last_emitted) :]
            else:
                delta = content
            if not delta:
                continue
            answer_parts.append(delta)
            last_emitted = content
            yield delta

        # 取会话历史存储对象（按 session_id 隔离）。
        history = get_session_history(context.session_id)
        # 记录本轮用户输入。
        history.add_user_message(context.user_prompt)
        # 记录本轮模型最终回答（不包含 systemPrompt / tool）。
        final_answer = "".join(answer_parts).strip()
        # 空回答不写入，避免历史中出现空 assistant 消息导致下游报错。
        if final_answer:
            history.add_ai_message(final_answer)
