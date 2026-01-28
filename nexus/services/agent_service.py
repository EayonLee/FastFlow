import asyncio
import json
from typing import AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from nexus.common.exceptions import BusinessError
from nexus.core.schemas import BuilderContext, Operation, LogicalGraph
from nexus.agents.builder import BuilderAgent
from nexus.agents.chat import ChatAgent
from nexus.agents.helpers.layouter import Layouter
from nexus.core.registry import registry
from nexus.core.graph_ops import apply_operations
from nexus.core.validators import validate_graph
from nexus.config.logger import get_logger
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

logger = get_logger(__name__)


class BuilderFlowState(TypedDict):
    # Builder 前端传递过来的请求上下文
    context: BuilderContext
    # 可用节点
    available_nodes: List
    # Builder 产出的结构化计划
    plan: Optional[Dict]
    # 解析后的 Operation 实例列表
    operations: List[Operation]
    # 错误信息，非空则流程提前结束
    error: Optional[str]
    # 统一 SSE 输出的回调
    emit: Callable[[str], Awaitable[None]]

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
            logger.error(f"ChatAgent error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': e.message}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"ChatAgent error with session_id: {context.session_id}, user_prompt: {context.user_prompt}, error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        # 发送 SSE 结束信号
        yield "data: [DONE]\n\n"


    async def handle_builder_request(self, context: BuilderContext) -> AsyncGenerator[str, None]:
        """处理构建型智能体请求"""
        # 通过队列把 LangGraph 结果流式发送给外部
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def emit_event(payload: Dict[str, object]):
            # 统一 SSE 数据格式
            await queue.put(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n")

        async def emit_chunk(content: str):
            # 输出模型流式思考
            await emit_event({"type": "chunk", "content": content})

        async def emit_error(message: object):
            # 输出错误信息
            await emit_event({"type": "error", "message": message})

        async def emit_layout(data: Dict[str, Dict[str, int]]):
            # 输出布局信息
            await emit_event({"type": "layout", "data": data})

        async def emit_graph(data: Dict):
            # 输出最终图
            await emit_event({"type": "graph", "data": data})

        async def emit_diff(data: Dict[str, int]):
            # 输出变更摘要
            await emit_event({"type": "diff", "data": data})

        async def load_available_node(state: BuilderFlowState):
            """
            第 1 步：加载可用节点列表。
            """
            try:
                logger.info("BuilderAgent flow [load_available_node] - start. session_id=%s", context.session_id)
                nodes = registry.get_all_nodes(context.auth_token)
                logger.info(
                    "BuilderAgent flow [load_available_node] - done. node_count=%d session_id=%s",
                    len(nodes),
                    context.session_id,
                )
                return {"available_nodes": nodes}
            except Exception as exc:
                logger.error("BuilderAgent flow [load_available_node] - failed: %s", exc)
                await emit_error(str(exc))
                return {"error": str(exc)}

        async def build_operation_plan(state: BuilderFlowState):
            """第 2 步：调用 BuilderAgent 生成操作计划。"""
            if state.get("error"):  # 上游已出错则跳过，直接返回空状态给下一步流程
                return {}

            logger.info("BuilderAgent flow [build_operation_plan] - start. session_id=%s", context.session_id)

            # 存放最终结构化计划
            final_plan = None
            try:
                # 流式获取模型输出的计划
                async for chunk in self.builder_agent.aplan(context, state["available_nodes"]):
                    # 判断当前chunk是否为结构化数据，只有结构化数据才保存到final_plan
                    if isinstance(chunk, dict):
                        # 如果是错误，则直接返回错误，终止流程，不做降级
                        if chunk.get("error"):
                            await emit_error(chunk.get("error"))
                            return {"error": chunk.get("error")}
                        final_plan = chunk 
                    else:
                        # 非结构化数据，直接流式输出给前端
                        await emit_chunk(str(chunk))
            except Exception as e:
                logger.error(
                    "BuilderAgent flow [build_operation_plan] - planning error session_id=%s prompt=%s error=%s",
                    context.session_id,
                    context.user_prompt,
                    e,
                )
                await emit_error(str(e))
                return {"error": str(e)}

            # 未拿到结构化的计划，则直接降级为 ChatAgent
            if not final_plan:
                logger.info(
                    "BuilderAgent flow [build_operation_plan] - no plan, fallback to ChatAgent, session_id=%s",
                    context.session_id,
                )

                # 回退为聊天模式
                async for chunk in self.chat_agent.achat(context):
                    # 转发聊天输出
                    await emit_chunk(str(chunk))
                # 标记降级
                return {"error": "fallback_to_chat"}

            logger.info(
                "BuilderAgent flow [build_operation_plan] - done. plan=%s session_id=%s",
                final_plan,
                context.session_id,
            )

            # 返回结构化计划给下一步
            return {"plan": final_plan}

        async def validate_operation_plan(state: BuilderFlowState):
            """第 3 步：校验并解析 Operation。"""

            # 上游已出错则跳过, 返回空状态给下一步
            if state.get("error"):
                return {}

            logger.info("BuilderAgent flow [validate_operation_plan] - start. session_id=%s", context.session_id)

            # 取出上一步大模型生成的原始操作列表
            operations_data = state["plan"].get("operations", []) if state.get("plan") else []
            # 存放结构化校验后的操作列表
            operations: List[Operation] = []
            try:
                for op in operations_data:
                    if isinstance(op, Operation):
                        operations.append(op)
                    else:
                        # 尝试解析为 Operation，若失败则退出当前整个流程
                        operations.append(Operation(**op))
            except Exception as exc:
                await emit_error(str(exc))  # 推送错误事件
                return {"error": str(exc)}  # 中断流程

            logger.info(
                "BuilderAgent flow [validate_operation_plan] - done. operations=%s session_id=%s",
                operations,
                context.session_id,
            )
            return {"operations": operations}  # 返回解析后的操作列表

        async def apply_plan_and_emit_graph(state: BuilderFlowState):  # 函数说明
            # 上游已出错则跳过，直接返回空状态给下一步流程
            if state.get("error"):
                return {}

            try:
                logger.info("BuilderAgent flow [apply_plan_and_emit_graph] - start. session_id=%s", context.session_id)
                # 统一对通过前端传递的当前图进行 model_dump 重新构造，避免 Pydantic 类型混用导致校验异常
                current_graph = LogicalGraph.model_validate(
                    context.current_graph.model_dump()
                )

                # 将操作应用到当前图上，生成新图和摘要
                apply_result = apply_operations(current_graph, state["operations"])
                # 取出最终图
                final_graph = apply_result.graph

                # 若有应用错误，记录错误并中断流程
                if apply_result.errors:
                    error_msgs = [
                        e.model_dump() if hasattr(e, "model_dump") else str(e)
                        for e in apply_result.errors
                    ]
                    await emit_error(error_msgs)  # 推送错误事件
                    return {"error": "apply_operations failed"}  # 中断流程

                # 对新图进行校验，确保图结构符合要求
                errors = validate_graph(final_graph)
                if errors:
                    logger.error(
                        "BuilderAgent flow [apply_plan_and_emit_graph] - graph validation failed session_id=%s errors=%s",
                        context.session_id,
                        "; ".join(errors),
                    )
                    await emit_error("; ".join(errors))  # 推送错误事件
                    return {"error": "graph validation failed"}  # 中断流程

                # 变更摘要
                diff_summary = {
                    "applied_ops": apply_result.applied_ops,  # 实际应用操作数
                    "total_ops": len(state["operations"]),  # 计划操作数
                    "node_count": len(final_graph.nodes),  # 节点数量
                    "edge_count": len(final_graph.edges),  # 边数量
                }

                # 计算布局
                positions = self.layouter.layout(final_graph)
                # 若布局有效，更新节点位置
                if positions:
                    for node in final_graph.nodes:
                        coords = positions.get(node.id)  # 获取节点坐标
                        if coords is not None:  # 坐标存在才写入
                            node.data = node.data or {}
                            node.data["position"] = coords  # 坐标写入 data，符合前端约定

                # 推送布局事件
                await emit_layout(positions)

                # 推送最终图事件
                await emit_graph(final_graph.model_dump())

                # 推送变更摘要
                await emit_diff(diff_summary)

                logger.info(
                    "BuilderAgent flow [apply_plan_and_emit_graph] - done. applied_ops=%d final_graph=%s diff_summary=%s session_id=%s",
                    apply_result.applied_ops,
                    final_graph.model_dump_json(),
                    diff_summary,
                    context.session_id,
                )
            except Exception as exc:
                logger.error("BuilderAgent flow [apply_plan_and_emit_graph] - error: %s", exc)
                await emit_error(f"BuilderAgent apply plan error: {str(exc)}")
                return {"error": str(exc)}

            return {}

        def route_if_error(state: BuilderFlowState) -> str:
            # 如果错误已发生，直接结束
            return "__end__" if state.get("error") else "next"

        # 定义执行流的 StateGraph
        workflow = StateGraph(BuilderFlowState)

        # 添加节点
        workflow.add_node("load_available_node", load_available_node) 
        workflow.add_node("build_operation_plan", build_operation_plan)
        workflow.add_node("validate_operation_plan", validate_operation_plan)
        workflow.add_node("apply_plan_and_emit_graph", apply_plan_and_emit_graph)

        # 定义 BuilderAgent 的执行流，set_entry_point 代表设置入口节点
        workflow.set_entry_point("load_available_node")
        # 第 1 步：加载可用节点列表 -> 第 2 步：计划操作
        workflow.add_conditional_edges("load_available_node", route_if_error, {"next": "build_operation_plan", "__end__": END})
        # 第 2 步：计划操作 -> 第 3 步：校验并解析 Operation
        workflow.add_conditional_edges("build_operation_plan", route_if_error, {"next": "validate_operation_plan", "__end__": END})
        # 第 3 步：校验并解析 Operation -> 第 4 步：应用操作，生成最终图与布局
        workflow.add_conditional_edges("validate_operation_plan", route_if_error, {"next": "apply_plan_and_emit_graph", "__end__": END})
        # 第 4 步：应用操作，生成最终图与布局 -> 结束
        workflow.add_edge("apply_plan_and_emit_graph", END)

        # 编译 StateGraph 为可执行应用
        app = workflow.compile()

        # 异步执行，用于驱动 LangGraph 执行并保证最终输出 DONE
        async def run_flow():
            try:
                await app.ainvoke(
                    {
                        "context": context,
                        "available_nodes": [],
                        "plan": None,
                        "operations": [],
                        "error": None,
                        "emit": emit_event,
                    }
                )
            except Exception as exc:
                logger.error("BuilderAgent flow - error: %s", exc)
                await emit_error(str(exc))
            finally:
                await queue.put("data: [DONE]\n\n")

        # 启动异步任务
        task = asyncio.create_task(run_flow())

        while True:
            # 按顺序把事件流发送出去
            message = await queue.get()
            yield message
            if message == "data: [DONE]\n\n":
                break

        await task
