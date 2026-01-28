import uuid
from typing import Annotated, List, Literal, Union, Dict, Any, AsyncGenerator, Optional
from pydantic import BaseModel, Field, ValidationError

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolCall, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from nexus.core.prompts import BUILDER_SYSTEM_PROMPT
from nexus.agents.helpers.tools import build_agent_tools
from nexus.core.schemas import BuilderContext, Operation, NodeDefinition, OpType
from nexus.core.llm_factory import get_or_create_llm
from nexus.config.logger import get_logger

logger = get_logger(__name__)

class BuilderState(TypedDict):
    """
    构建智能体状态，包含对话历史、最终计划和计划错误。
    """
    # LangGraph 会在 messages 上进行对话历史追加
    messages: Annotated[List[BaseMessage], "add_messages"]
    # 最终由 submit_plan 抽取并校验后的结果
    final_plan: Optional[Dict[str, Any]]
    # submit_plan 校验错误（用于触发重试）
    plan_error: Optional[str]

class SubmitPlanInput(BaseModel):
    """
    提交计划的输入参数，包含思考和操作列表。
    """
    thought: str = Field(..., description="你对这些操作的推理过程")
    operations: List[Operation] = Field(..., description="要执行的操作列表")


class BuilderAgent:
    """
    负责将用户意图转换为图操作的智能体，使用 ReAct（推理 + 执行）循环通过 LangGraph 实现。
    """

    def __init__(self):
        pass

    async def aplan(self, context: BuilderContext, available_nodes: List[NodeDefinition]) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """
        执行构建智能体循环。
        在执行过程中会产生推理过程（思考），在结束时产生一个 最终计划。

        :param context: 构建智能体上下文
        :param available_nodes: 可添加到图中的可用节点类型列表
        :return: 异步生成器，每次迭代产生一个推理过程（思考）或最终计划
        """

        # 构建工具列表和实现
        tools, tool_impl = build_agent_tools(context, available_nodes, SubmitPlanInput)

        try:
            # 初始化模型并绑定工具
            llm = get_or_create_llm(context.model_config_id, context.auth_token, tools)
        except Exception as e:
            logger.error("BuilderAgent plan - failed to initialize LLM: %s", e)
            yield f"Error initializing AI model: {e}"
            return

        def agent_node(state: BuilderState):
            """
            让模型在当前消息上下文上生成下一步。
            """

            messages = state["messages"]
            logger.info(
                "BuilderAgent plan.agent_node - messages=%d session_id=%s",
                len(messages),
                context.session_id,
            )
            response = llm.invoke(messages)
            if response.tool_calls:
                logger.info(
                    "BuilderAgent plan.agent_node - tool_calls=%s session_id=%s",
                    response.tool_calls,
                    context.session_id,
                )
            return {"messages": [response]}

        tool_node = ToolNode(tools)

        def router(state: BuilderState) -> Literal["tools", "finalize", "__end__"]:
            """
            根据模型输出决定下一跳：工具调用 / 结束。
            :param state: 构建智能体状态，包含对话历史、最终计划和计划错误
            :return: 下一跳路由，"tools" 表示调用工具，"finalize" 表示提交计划，"__end__" 表示结束
            """
            # 根据模型输出决定下一跳：工具调用 / 结束
            messages = state["messages"]
            last_message = messages[-1]

            if not isinstance(last_message, AIMessage):
                return "__end__"

            if not last_message.tool_calls:
                return "__end__"

            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "submit_plan":
                    return "finalize"

            return "tools"

        def _has_edge_for_node(operations: List[Operation], node_id: Optional[str]) -> bool:
            """
            检查操作列表中是否有针对指定节点的边操作。
            :param operations: 操作列表
            :param node_id: 节点 ID，若为 None 则检查是否有添加边操作
            :return: 如果有针对该节点的边操作或添加边操作，则返回 True，否则返回 False
            """
            if not node_id:
                return any(op.op_type == OpType.ADD_EDGE for op in operations)
            for op in operations:
                if op.op_type == OpType.ADD_EDGE:
                    if op.params.get("source") == node_id or op.params.get("target") == node_id:
                        return True
            return False

        def _normalize_new_node_ids(operations: List[Operation]) -> Dict[str, str]:
            """
            为新增节点补齐 ObjectId，并建立占位符映射。
            :param operations: 操作列表
            :return: 占位符映射，键为占位符，值为对应的节点 ID
            """
            mapping: Dict[str, str] = {}
            counter = 0
            for op in operations:
                if op.op_type != OpType.ADD_NODE:
                    continue
                node_id = op.params.get("id") or op.target_id
                if not node_id:
                    counter += 1
                    node_id = uuid.uuid4().hex[:24]
                    op.params["id"] = node_id
                    op.target_id = node_id
                else:
                    op.params["id"] = node_id
                    op.target_id = node_id
                # 记录可能的占位符映射
                if op.op_id and op.op_id not in mapping:
                    mapping[op.op_id] = node_id
            return mapping

        def _resolve_edge_placeholders(
            operations: List[Operation],
            placeholder_map: Dict[str, str],
            existing_node_ids: set,
        ) -> bool:
            """
            修复 ADD_EDGE 中的占位符，返回是否全部可解析。
            :param operations: 操作列表
            :param placeholder_map: 占位符映射，键为占位符，值为对应的节点 ID
            :param existing_node_ids: 已存在的节点 ID 集合
            :return: 如果所有边操作中的占位符都能解析，则返回 True，否则返回 False
            """
            new_node_ids = {
                op.params.get("id") or op.target_id
                for op in operations
                if op.op_type == OpType.ADD_NODE
            }
            unknown_refs = []
            for op in operations:
                if op.op_type != OpType.ADD_EDGE:
                    continue
                for key in ("source", "target"):
                    value = op.params.get(key)
                    if not value:
                        continue
                    if value in existing_node_ids or value in new_node_ids:
                        continue
                    resolved = None
                    if value in placeholder_map:
                        resolved = placeholder_map[value]
                    elif value.startswith("__new_") or value.endswith("_NEW"):
                        if len(new_node_ids) == 1:
                            resolved = next(iter(new_node_ids))
                    if resolved:
                        op.params[key] = resolved
                    else:
                        unknown_refs.append(value)
            if unknown_refs:
                logger.error(
                    "BuilderAgent finalize_node - unresolved edge refs=%s",
                    unknown_refs,
                )
                return False
            return True

        def finalize_node(state: BuilderState):
            """
            从 submit_plan 工具调用中提取并验证计划。
            :param state: 构建智能体状态，包含对话历史、最终计划和计划错误
            :return: 更新后的状态，包含最终计划和计划错误
            """
            messages = state["messages"]
            last_message = messages[-1]
            logger.info(
                "BuilderAgent plan.finalize_node - tool_calls=%s session_id=%s",
                last_message.tool_calls,
                context.session_id,
            )

            # 只从 submit_plan 抽取结构化输出
            final_plan = None
            for tool_call in last_message.tool_calls:
                if tool_call["name"] == "submit_plan":
                    final_plan = tool_call.get("args")
                    break

            if not final_plan:
                return {"final_plan": None, "plan_error": None}

            # 记录模型原始输出，便于排查 add/update 行为
            logger.info(
                "BuilderAgent plan.finalize_node - submit_plan raw args=%s session_id=%s",
                final_plan,
                context.session_id,
            )

            # 预处理 REMOVE_EDGE：允许仅给 target_id 的简写形式
            operations_raw = final_plan.get("operations", []) if isinstance(final_plan, dict) else []
            for op in operations_raw:
                if op.get("op_type") != OpType.REMOVE_EDGE.value:
                    continue
                params = op.get("params") or {}
                if params.get("source") and params.get("target"):
                    continue
                target_id = op.get("target_id")
                if isinstance(target_id, str):
                    if "--" in target_id:
                        source, target = target_id.split("--", 1)
                        params.setdefault("source", source)
                        params.setdefault("target", target)
                        op["params"] = params
                    elif "_" in target_id and target_id.count("_") == 1:
                        source, target = target_id.split("_", 1)
                        params.setdefault("source", source)
                        params.setdefault("target", target)
                        op["params"] = params

            # 对模型输出进行 Pydantic 校验，保证 Operation 结构正确
            try:
                validated = SubmitPlanInput.model_validate(final_plan)
            except ValidationError as exc:
                logger.error(
                    "BuilderAgent plan.finalize_node - invalid plan: %s session_id=%s",
                    exc,
                    context.session_id,
                )
                # 用 HumanMessage 反馈错误，避免 tool_call_id 不匹配导致 400
                error_msg = (
                    "submit_plan 参数不合法，请补全必填字段后重试。"
                    "特别注意：REMOVE_EDGE 需要 source/target。"
                )
                return {
                    "messages": [HumanMessage(content=error_msg)],
                    "final_plan": None,
                    "plan_error": str(exc),
                }

            # 统一将 Operation 转为 dict 便于后续序列化
            operations = []
            for op in validated.operations:
                if isinstance(op, Operation):
                    operations.append(op.model_dump())
                else:
                    operations.append(Operation.model_validate(op).model_dump())

            # 通过操作列表补齐新增节点 ID，并修复边引用占位符
            existing_node_ids = set()
            if context.current_graph:
                existing_node_ids = {node.id for node in context.current_graph.nodes}
            placeholder_map = _normalize_new_node_ids(validated.operations)
            if not _resolve_edge_placeholders(validated.operations, placeholder_map, existing_node_ids):
                error_msg = "新增节点的连线引用了未知 ID，请补全正确的 source/target。"
                return {
                    "messages": [HumanMessage(content=error_msg)],
                    "final_plan": None,
                    "plan_error": error_msg,
                }

            # 连接性约束：新增节点必须有至少一条关联边
            for op in validated.operations:
                if op.op_type == OpType.ADD_NODE:
                    node_id = op.params.get("id") or op.target_id
                    if not _has_edge_for_node(validated.operations, node_id):
                        error_msg = "新增节点必须至少连接一条边，请补充连线。"
                        return {
                            "messages": [HumanMessage(content=error_msg)],
                            "final_plan": None,
                            "plan_error": error_msg,
                        }

            return {
                "final_plan": {"thought": validated.thought, "operations": operations},
                "plan_error": None,
            }

        def load_available_node(state: BuilderState):
            """
            从工具调用中加载可用节点列表。
            :param state: 构建智能体状态，包含对话历史、最终计划和计划错误
            :return: 更新后的状态，包含可用节点列表
            """
            # 首轮强制通过工具获取上下文，避免依赖 prompt 注入
            # 这里手动执行工具并构造 ToolMessage，确保 tool_call_id 对齐
            node_catalog = tool_impl.get_node_catalog()
            current_graph = tool_impl.get_current_graph()

            messages = [
                SystemMessage(content=BUILDER_SYSTEM_PROMPT),
                HumanMessage(content=context.user_prompt),
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(name="get_node_catalog", args={}, id="call_node_catalog"),
                        ToolCall(name="get_current_graph", args={}, id="call_current_graph"),
                    ],
                ),
                ToolMessage(content=node_catalog, tool_call_id="call_node_catalog"),
                ToolMessage(content=current_graph, tool_call_id="call_current_graph"),
            ]
            return {"messages": messages}

        # 构建 ReAct 主循
        workflow = StateGraph(BuilderState)

        # 定义节点
        workflow.add_node("load_available_node", load_available_node)
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.add_node("finalize", finalize_node)

        # 定义入口节点
        workflow.set_entry_point("load_available_node")
        # 首轮上下文已在 load_available_node 内获取，直接进入 agent
        workflow.add_edge("load_available_node", "agent")
        # 后续仍可通过工具循环调用，直到生成 submit_plan 或失败
        workflow.add_edge("tools", "agent")
        workflow.add_conditional_edges("agent", router)

        def finalize_router(state: BuilderState) -> Literal["agent", "__end__"]:
            # submit_plan 校验失败则结束并带上错误，交给上游处理
            return "__end__" if state.get("final_plan") or state.get("plan_error") else "agent"
        # 定义最终节点路由
        workflow.add_conditional_edges("finalize", finalize_router)

        app = workflow.compile()

        # 初始输入为空，由 load_available_node 生成首轮消息
        inputs = {"messages": [], "final_plan": None}

        async for event in app.astream_events(inputs, version="v1"):
            event_type = event["event"]

            if event_type == "on_chat_model_stream":
                # 流式输出模型思考片段
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
            elif event_type == "on_tool_start":
                # 标注工具调用阶段，便于前端展示
                tool_name = event["name"]
                if tool_name == "get_node_catalog":
                    yield "\n> Checking Node Catalog...\n"
                elif tool_name == "get_current_graph":
                    yield "\n> Inspecting Current Graph...\n"
            elif event_type == "on_chain_end" and event["name"] == "finalize":
                # 提取最终结构化计划
                output = event["data"]["output"]
                if output:
                    if output.get("final_plan"):
                        yield output["final_plan"]
                    elif output.get("plan_error"):
                        yield {"error": output.get("plan_error")}
