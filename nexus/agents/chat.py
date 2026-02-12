from typing import AsyncGenerator
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from nexus.core.schemas import BuilderContext
from langchain_core.runnables.history import RunnableWithMessageHistory
from nexus.core.memory import get_session_history
from nexus.core.llm_factory import get_or_create_llm
from nexus.core.prompts import CHAT_SYSTEM_PROMPT
from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger

logger = get_logger(__name__)


class ChatAgent:
    """
    通用对话 Agent。
    """
    
    def __init__(self):
        # 定义基础的 Prompt 模板
        self.prompt = ChatPromptTemplate.from_messages([
            # 系统角色，定义助手的行为和能力
            ("system", CHAT_SYSTEM_PROMPT),
            # 历史消息占位符，用于存储对话历史
            MessagesPlaceholder(variable_name="history"),
            # 用户输入占位符，用于接收用户的问题或指令
            ("human", "{user_prompt}"),
        ])

    def _get_runnable(self, context: BuilderContext):
        """
        获取或创建一个 RunnableWithMessageHistory 实例。
        
        :param context: 包含模型配置、用户提示等信息的上下文对象
        :return: 配置好的 RunnableWithMessageHistory 实例
        """
        config_id = context.model_config_id
        if not config_id:
            raise BusinessError("缺少模型配置 ID (model_config_id)")

        # 1. 获取共享的 LLM 实例
        llm = get_or_create_llm(config_id, context.auth_token)

        # 2. 组装 Chain
        chain = self.prompt | llm

        # 3. 包装 History
        return RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="user_prompt",
            history_messages_key="history",
        )

    async def achat(self, context: BuilderContext) -> AsyncGenerator[str, None]:
        """
        处理流式对话请求。
        :param context: 包含模型配置、用户提示等信息的上下文对象
        :return: 异步生成器，每次yield一个对话片段
        """

        runnable = self._get_runnable(context)

        # 序列化当前图数据
        graph_json = "{}"
        if context.current_graph:
            graph_json = context.current_graph.model_dump_json()

        # 处理流式响应
        async for chunk in runnable.astream(
                # 占位符替换
                {
                    "user_prompt": context.user_prompt,
                    "current_graph": graph_json
                },
                # 指定会话ID，实现历史记录的隔离
                config={"configurable": {"session_id": context.session_id}}
        ):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)
