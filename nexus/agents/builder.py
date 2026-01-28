from typing import List, AsyncGenerator
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser

from core.schemas import BuilderContext, Operation, NodeDefinition
from langchain_core.runnables.history import RunnableWithMessageHistory
from core.memory import get_session_history
from core.llm_factory import get_or_create_llm
from core.prompts import BUILDER_SYSTEM_PROMPT
from common.exceptions import BusinessError
from config.logger import get_logger

logger = get_logger(__name__)

class PlanResponse(BaseModel):
    """
    LLM 输出的结构化响应，包含一系列操作。
    """
    thought: str = Field(..., description="规划过程的思考，解释为什么需要这些操作")
    operations: List[Operation] = Field(..., description="要执行的操作序列")

class BuilderAgent:
    """
    核心 Agent，负责将用户意图转化为图操作。
    对应架构中的 'Planner'（规划者）角色。
    
    支持多会话记忆和流式输出。
    支持动态模型切换和动态 API Key。
    """
    
    def __init__(self):
        # 移除实例级缓存，使用全局缓存
        self.parser = PydanticOutputParser(pydantic_object=PlanResponse)
        
        # 2. 构建 Prompt 模板 (支持 History)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{user_prompt}"),
        ])
        
    def _get_runnable(self, context: BuilderContext):
        """
        根据上下文获取或创建 Runnable。
        支持动态获取 API Key 和模型配置。
        """
        config_id = context.model_config_id
        if not config_id:
            raise BusinessError("上下文缺少模型配置 ID (Model Config ID)")
            
        # 1. 获取共享的 LLM 实例 (缓存优化)
        llm = get_or_create_llm(config_id, context.auth_token)

        # 2. 绑定特定参数 (JSON Mode)
        # 注意：使用 bind 不会修改原始 llm 实例，而是返回一个新的 Runnable
        llm_with_config = llm.bind(response_format={"type": "json_object"})

        # 3. 组装 Chain (Prompt | LLM)
        chain = self.prompt | self.llm_chain(llm_with_config)

        # 4. 包装 History (轻量级包装，无需缓存)
        return RunnableWithMessageHistory(
            chain,
            get_session_history,
            input_messages_key="user_prompt",
            history_messages_key="history",
        )

    def llm_chain(self, llm):
        return llm

    async def aplan(self, context: BuilderContext, available_nodes: List[NodeDefinition]) -> AsyncGenerator[str, None]:
        """
        异步流式规划。
        """
        # 1. 准备上下文
        runnable = self._get_runnable(context)
        
        # 2. 构造 Prompt 输入、将节点定义列表序列化为文本
        nodes_text = self._serialize_nodes(available_nodes)
        
        # 序列化当前图数据
        graph_json = "{}"
        if context.current_graph:
            graph_json = context.current_graph.model_dump_json()
        
        # 3. 构造系统提示词
        system_prompt = self._construct_system_prompt(nodes_text, graph_json)
        
        # 4. 准备输入变量
        input_vars = {
            "system_prompt": system_prompt,
            "user_prompt": context.user_prompt,
        }

        # 3. 流式调用 LLM
        async for chunk in runnable.astream(
            input_vars,
            config={"configurable": {"session_id": context.session_id}}
        ):
            # 提取内容 (chunk 是 BaseMessageChunk)
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)
                

    def _serialize_nodes(self, nodes: List[NodeDefinition]) -> str:
        """
        将节点定义列表序列化为文本格式，用于Builder智能体的系统提示词。
        
        :param nodes: 节点定义列表
        :return: 格式化后的节点文本
        """
        lines = []
        for node in nodes:
            # TODO: 丰富 schema 描述
            lines.append(f"- 类型: {node.type}, 名称: {node.label}, 分类: {node.category}")
        return "\n".join(lines)

    def _construct_system_prompt(self, nodes_text: str, current_graph_json: str) -> str:
        """
        构造 Builder 智能体的系统提示词。
        
        :param nodes_text: 节点定义文本
        :param current_graph_json: 当前工作流上下文 JSON 字符串
        :return: 格式化后的系统提示词
        """
        return BUILDER_SYSTEM_PROMPT.format(
            nodes_text=nodes_text,
            current_graph=current_graph_json
        )
