import asyncio
import json
import sys
import time
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nexus.core.schemas import ChatRequestContext, ExecutionHints
from nexus.core.agent_runtime.cancellation import RunCancellationContext, RunCancelledError
from nexus.core.tools.runtime.contracts import TOOL_CALL_SOURCE_HINT, ToolCatalog, ToolExecutionSpec
from nexus.core.tools.runtime.executor import ToolExecutor
from nexus.core.tools.runtime.planner import build_hint_tool_message


def _isolated_echo_runner(tool_args):
    return {"value": tool_args["value"]}


def _isolated_sleep_runner(tool_args):
    time.sleep(float(tool_args.get("sleep_seconds", 0)))
    return {"slept": True}


def _build_catalog(*tools) -> ToolCatalog:
    return ToolCatalog(
        tools=list(tools),
        registry_by_name={tool_item.name: tool_item for tool_item in tools},
        execution_specs_by_name={tool_item.name: ToolExecutionSpec(tool=tool_item) for tool_item in tools},
        workflow_tool_count=0,
        skill_tool_count=0,
        time_tool_count=0,
    )


def test_build_hint_tool_message_from_execution_hints():
    catalog = ToolCatalog(
        tools=[],
        registry_by_name={
            "get_workflow_node_summary": object(),
            "load_skill": object(),
        },
        workflow_tool_count=0,
        skill_tool_count=0,
        time_tool_count=0,
    )
    context = ChatRequestContext(
        user_prompt="",
        execution_hints=ExecutionHints(
            selected_nodes=[" node-1 ", "node-1"],
            selected_skills=["skill-a", "skill-a"],
        ),
        workflow_graph='{"nodes":[{"nodeId":"node-1","flowNodeType":"tool"}],"edges":[],"chatConfig":{}}',
        model_config_id=10003,
    )

    message = build_hint_tool_message(context, catalog)

    assert message is not None
    assert message.additional_kwargs["tool_call_source"] == TOOL_CALL_SOURCE_HINT
    assert [tool_call["name"] for tool_call in message.tool_calls] == [
        "get_workflow_node_summary",
        "load_skill",
    ]
    assert message.tool_calls[0]["args"] == {"node_id": "node-1"}
    assert message.tool_calls[1]["args"] == {"skill_name": "skill-a"}


def test_build_hint_tool_message_only_requires_tools_for_present_hints():
    catalog = ToolCatalog(
        tools=[],
        registry_by_name={"load_skill": object()},
        workflow_tool_count=0,
        skill_tool_count=0,
        time_tool_count=0,
    )
    context = ChatRequestContext(
        user_prompt="",
        execution_hints=ExecutionHints(selected_skills=["skill-a"]),
        model_config_id=10003,
    )

    message = build_hint_tool_message(context, catalog)

    assert message is not None
    assert [tool_call["name"] for tool_call in message.tool_calls] == ["load_skill"]


def test_build_hint_tool_message_requires_non_empty_workflow_graph_for_selected_nodes():
    catalog = ToolCatalog(
        tools=[],
        registry_by_name={"get_workflow_node_summary": object()},
        workflow_tool_count=0,
        skill_tool_count=0,
        time_tool_count=0,
    )
    context = ChatRequestContext(
        user_prompt="",
        execution_hints=ExecutionHints(selected_nodes=["node-1"]),
        workflow_graph="",
        model_config_id=10003,
    )

    try:
        build_hint_tool_message(context, catalog)
        raise AssertionError("expected BusinessError")
    except Exception as error:
        assert str(error) == "selected_nodes requires a non-empty workflow_graph"


def test_tool_executor_executes_and_dedupes_tool_calls():
    @tool
    def echo_value(value: str):
        """Return the provided value as JSON."""
        return json.dumps({"value": value}, ensure_ascii=False)

    executor = ToolExecutor(_build_catalog(echo_value), timeout_seconds=1)
    message = AIMessage(
        content="",
        additional_kwargs={"tool_call_source": "hint"},
        tool_calls=[
            {"name": "echo_value", "args": {"value": "hello"}, "id": "call_1"},
            {"name": "echo_value", "args": {"value": "hello"}, "id": "call_2"},
        ],
    )

    result = asyncio.run(executor.execute_ai_message(message))

    assert len(result) == 1
    tool_message = result[0]
    assert tool_message.tool_call_id == "call_1"
    assert tool_message.status == "success"
    assert tool_message.additional_kwargs["tool_call_source"] == "hint"
    assert json.loads(tool_message.content)["value"] == "hello"


def test_tool_executor_supports_isolated_process_execution():
    @tool
    def isolated_echo(value: str):
        """Return the provided value via isolated process."""
        return json.dumps({"value": value}, ensure_ascii=False)

    executor = ToolExecutor(
        ToolCatalog(
            tools=[isolated_echo],
            registry_by_name={isolated_echo.name: isolated_echo},
            execution_specs_by_name={
                isolated_echo.name: ToolExecutionSpec(
                    tool=isolated_echo,
                    mode="isolated_process",
                    process_target=_isolated_echo_runner,
                )
            },
        ),
        timeout_seconds=2,
    )
    message = AIMessage(
        content="",
        tool_calls=[{"name": "isolated_echo", "args": {"value": "hello"}, "id": "call_1"}],
    )

    result = asyncio.run(executor.execute_ai_message(message))

    assert len(result) == 1
    assert json.loads(result[0].content)["value"] == "hello"


def test_tool_executor_cancels_isolated_process_execution():
    @tool
    def isolated_sleep(sleep_seconds: float):
        """Sleep in isolated process."""
        return json.dumps({"slept": True}, ensure_ascii=False)

    cancellation_context = RunCancellationContext()
    executor = ToolExecutor(
        ToolCatalog(
            tools=[isolated_sleep],
            registry_by_name={isolated_sleep.name: isolated_sleep},
            execution_specs_by_name={
                isolated_sleep.name: ToolExecutionSpec(
                    tool=isolated_sleep,
                    mode="isolated_process",
                    process_target=_isolated_sleep_runner,
                )
            },
        ),
        timeout_seconds=5,
        cancellation_context=cancellation_context,
    )
    message = AIMessage(
        content="",
        tool_calls=[{"name": "isolated_sleep", "args": {"sleep_seconds": 5}, "id": "call_1"}],
    )

    async def _run():
        task = asyncio.create_task(executor.execute_ai_message(message))
        await asyncio.sleep(0.2)
        cancellation_context.cancel("用户主动停止生成")
        await task

    try:
        asyncio.run(_run())
        raise AssertionError("expected RunCancelledError")
    except RunCancelledError as error:
        assert str(error) == "用户主动停止生成"


def test_tool_executor_returns_error_message_for_unknown_tool():
    executor = ToolExecutor(_build_catalog(), timeout_seconds=1)
    message = AIMessage(
        content="",
        tool_calls=[{"name": "missing_tool", "args": {}, "id": "call_missing"}],
    )

    result = asyncio.run(executor.execute_ai_message(message))

    assert len(result) == 1
    tool_message = result[0]
    assert tool_message.status == "error"
    assert tool_message.additional_kwargs["tool_call_source"] == "model"
    assert "tool not found" in tool_message.content


def test_tool_executor_uses_default_timeout_from_settings():
    executor = ToolExecutor(_build_catalog())

    assert executor._timeout_seconds >= 1
