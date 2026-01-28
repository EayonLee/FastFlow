import json
from typing import AsyncGenerator

from common.exceptions import BusinessError
from core.schemas import BuilderContext, Operation, LogicalGraph
from agents.builder import BuilderAgent
from agents.chat import ChatAgent
from agents.layouter import Layouter
from core.registry import registry
from core.graph_ops import apply_operations
from config.logger import get_logger

logger = get_logger(__name__)

class AgentService:
    """
    智能体服务层，负责协调 ChatAgent 和 BuilderAgent 的执行逻辑。
    """

    def __init__(self, builder_agent: BuilderAgent, chat_agent: ChatAgent, layouter: Layouter):
        """
        初始化 AgentService。

        :param builder_agent: 构建型智能体实例
        :param chat_agent: 对话型智能体实例
        :param layouter: 布局器实例
        """
        self.builder_agent = builder_agent
        self.chat_agent = chat_agent
        self.layouter = layouter

    async def handle_chat_request(self, context: BuilderContext) -> AsyncGenerator[str, None]:
        """处理对话型智能体请求"""
        try:
            # 调用 ChatAgent 处理流式对话, 并将每个 chunk 包装为 SSE 格式
            async for chunk in self.chat_agent.achat(context):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        except BusinessError as e:
            logger.warning(f"Chat agent business error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.message}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"Chat agent error with session_id: {context.session_id}, user_prompt: {context.user_prompt}, error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        # 发送 SSE 结束信号
        yield "data: [DONE]\n\n"



    async def handle_builder_request(self, context: BuilderContext) -> AsyncGenerator[str, None]:
        """处理构建型智能体请求"""
        # 刷新节点列表
        registry.refresh_nodes(context.auth_token)
        nodes = registry.get_all_nodes()
        
        full_content = ""
        
        # 1. 产生思考和操作流
        try:
            # 调用 BuilderAgent 处理流式计划, 并将每个 chunk 包装为 SSE 格式
            async for chunk in self.builder_agent.aplan(context, nodes):
                full_content += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
        except BusinessError as e:
            logger.warning(f"Builder agent business error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.message}, ensure_ascii=False)}\n\n"
            return
        except Exception as e:
            logger.error(f"Builder agent planning error with session_id: {context.session_id}, user_prompt: {context.user_prompt}, error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        # 2. 尝试解析完整的 JSON 并执行后续操作
        try:
            # 简单的从累积字符串中提取 JSON
            # 注意：这里假设 LLM 输出的 JSON 是在流结束后完整的，或者在最后包含完整的 JSON
            # 实际情况中，builder_agent.aplan 可能已经返回了 clean 的内容，
            # 但这里沿用了原有逻辑：从 chunk 累积的内容中解析。
            
            # 尝试找到 JSON 的开始和结束
            # 如果 full_content 包含 Markdown 代码块，需要去除
            content_to_parse = full_content
            if "```json" in content_to_parse:
                content_to_parse = content_to_parse.split("```json")[1].split("```")[0]
            elif "```" in content_to_parse:
                content_to_parse = content_to_parse.split("```")[1].split("```")[0]

            response_data = json.loads(content_to_parse.strip())
            operations_data = response_data.get("operations", [])
            operations = [Operation(**op) for op in operations_data]

            if operations:
                # 模拟应用操作
                current_graph = context.current_graph or LogicalGraph()
                final_graph = apply_operations(current_graph, operations)

                # 计算布局
                positions = self.layouter.layout(final_graph)

                # 发送布局事件
                yield f"data: {json.dumps({'type': 'layout', 'data': positions}, ensure_ascii=False)}\n\n"

                # 发送最终图预览事件
                yield f"data: {json.dumps({'type': 'graph', 'data': final_graph.model_dump()}, ensure_ascii=False)}\n\n"

        except json.JSONDecodeError:
            # 如果不是 JSON，可能只是普通对话，不报错，或者记录日志
            logger.warning("Failed to parse JSON from builder response. It might be a conversational response.")
        except Exception as e:
            logger.error(f"Post-processing error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Post-processing error: {str(e)}'}, ensure_ascii=False)}\n\n"

        # 发送 SSE 结束信号
        yield "data: [DONE]\n\n"
