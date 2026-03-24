import asyncio
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nexus.common.exceptions import BusinessError
from nexus.core.agent_runtime.cancellation import RunCancellationContext, RunCancelledError
from nexus.core.agent_runtime.contracts import AgentRuntimeConfig
from nexus.core.schemas import ChatRequestContext, ExecutionHints
from nexus.core.tools.runtime.contracts import CHAT_AGENT_TOOL_PROFILE


def _reload_module(module_name):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _load_runtime_modules():
    turn_stream_module = _reload_module("nexus.core.agent_runtime.turn_stream")
    run_loop_module = _reload_module("nexus.core.agent_runtime.run_loop")
    chat_module = _reload_module("nexus.agents.chat")
    policy_module = _reload_module("nexus.core.policies.tool_use_policy")
    agent_service_module = _reload_module("nexus.services.agent_service")
    agent_api_module = _reload_module("nexus.api.agent")
    return turn_stream_module, run_loop_module, chat_module, policy_module, agent_service_module, agent_api_module


class FakeLLM:
    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, messages):
        for chunk in self._chunks:
            yield chunk


class DelayedFirstTokenLLM:
    def __init__(self, delay_seconds):
        self._delay_seconds = delay_seconds

    async def astream(self, messages):
        await asyncio.sleep(self._delay_seconds)
        yield AIMessage(content="迟到的首个流式事件")


class CancelAfterFirstChunkLLM:
    def __init__(self, cancellation_context):
        self._cancellation_context = cancellation_context

    async def astream(self, messages):
        yield AIMessageChunk(content="部分回答")
        self._cancellation_context.cancel("用户已停止生成")
        await asyncio.sleep(0)


class DummyHistory:
    def __init__(self):
        self.messages = []
        self.user_messages = []
        self.ai_messages = []

    def add_user_message(self, message):
        self.user_messages.append(message)

    def add_ai_message(self, message):
        self.ai_messages.append(message)


class DummyChatAgent:
    def __init__(self, events):
        self._events = events

    async def achat(self, context, cancellation_context=None):
        for event in self._events:
            yield event


class ErrorChatAgent:
    async def achat(self, context, cancellation_context=None):
        raise BusinessError("模型未返回有效回答")
        yield  # pragma: no cover


class CancelledChatAgent:
    async def achat(self, context, cancellation_context=None):
        if cancellation_context is not None:
            cancellation_context.cancel("用户已停止生成")
        raise RunCancelledError("用户已停止生成")
        yield  # pragma: no cover


async def _collect(async_iterable):
    events = []
    async for item in async_iterable:
        events.append(item)
    return events


def _build_runtime_config(context, cancellation_context=None):
    return AgentRuntimeConfig(
        agent_name="chat",
        context=context,
        system_prompt="system",
        tool_profile=CHAT_AGENT_TOOL_PROFILE,
        cancellation_context=cancellation_context,
    )


def _build_tool_catalog_stub(
    *,
    tools=None,
    workflow_tools=None,
    skill_tools=None,
    time_tools=None,
):
    tools = list(tools or [])
    workflow_tools = list(workflow_tools or [])
    skill_tools = list(skill_tools or [])
    time_tools = list(time_tools or [])
    registry_by_name = {
        str(getattr(tool, "name", "") or "").strip(): tool
        for tool in tools
        if str(getattr(tool, "name", "") or "").strip()
    }
    return SimpleNamespace(
        tools=tools,
        registry_by_name=registry_by_name,
        workflow_tools=workflow_tools,
        skill_tools=skill_tools,
        time_tools=time_tools,
        total_count=len(tools),
        workflow_tool_count=len(workflow_tools),
        skill_tool_count=len(skill_tools),
        time_tool_count=len(time_tools),
    )


def test_stream_model_turn_returns_internal_result(monkeypatch):
    turn_stream_module, _run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (FakeLLM([AIMessage(content="你好")]), None, "glm-5"),
    )

    context = ChatRequestContext(user_prompt="你好", model_config_id=10003)
    runtime_config = _build_runtime_config(context)
    messages = [SystemMessage(content="system"), HumanMessage(content="你好")]

    events = asyncio.run(
        _collect(
            turn_stream_module.stream_model_turn(
                runtime_config=runtime_config,
                config_id=10003,
                messages=messages,
                tool_catalog=_build_tool_catalog_stub(),
            )
        )
    )

    assert events[0]["type"] == "answer.delta"
    assert events[0]["content"] == "你好"
    assert events[-1]["type"] == turn_stream_module.INTERNAL_TURN_RESULT_EVENT
    assert events[-1]["result"].message.content == "你好"
    assert events[-1]["result"].message.tool_calls == []
    assert events[-1]["result"].streamed_answer_len == len("你好")


def test_stream_model_turn_times_out_on_first_token(monkeypatch):
    turn_stream_module, _run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (DelayedFirstTokenLLM(0.05), None, "glm-5"),
    )
    monkeypatch.setattr(turn_stream_module.settings, "MODEL_STREAM_FIRST_EVENT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(turn_stream_module.settings, "MODEL_STREAM_IDLE_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(turn_stream_module.settings, "MODEL_STREAM_TOTAL_TIMEOUT_SECONDS", 0.05)

    context = ChatRequestContext(user_prompt="你好", model_config_id=10003)
    runtime_config = _build_runtime_config(context)
    messages = [SystemMessage(content="system"), HumanMessage(content="你好")]

    try:
        asyncio.run(
            _collect(
                turn_stream_module.stream_model_turn(
                    runtime_config=runtime_config,
                    config_id=10003,
                    messages=messages,
                    tool_catalog=_build_tool_catalog_stub(),
                )
            )
        )
        raise AssertionError("expected BusinessError")
    except BusinessError as error:
        assert str(error) == "模型流式输出超时：首个流式事件返回过慢"


def test_stream_model_turn_splits_inline_thinking_tags_before_emitting_answer(monkeypatch):
    turn_stream_module, _run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (
            FakeLLM(
                [
                    AIMessageChunk(content="<think>\n用户"),
                    AIMessageChunk(content="问我是谁，这是一个简单问题。\n</think>\n\n我是 **Nexus**。"),
                ]
            ),
            None,
            "minimax-m2.5",
        ),
    )

    context = ChatRequestContext(user_prompt="你是谁？", model_config_id=10003)
    runtime_config = _build_runtime_config(context)
    messages = [SystemMessage(content="system"), HumanMessage(content="你是谁？")]

    events = asyncio.run(
        _collect(
            turn_stream_module.stream_model_turn(
                runtime_config=runtime_config,
                config_id=10003,
                messages=messages,
                tool_catalog=_build_tool_catalog_stub(),
            )
        )
    )

    answer_deltas = [event["content"] for event in events if event.get("type") == "answer.delta"]
    thinking_deltas = [event["content"] for event in events if event.get("type") == "thinking.delta"]
    turn_result = events[-1]["result"]

    assert "".join(thinking_deltas) == "用户问我是谁，这是一个简单问题。"
    assert "".join(answer_deltas) == "我是 **Nexus**。"
    assert "<think>" not in "".join(answer_deltas)
    assert "</think>" not in "".join(answer_deltas)
    assert turn_result.message.content == "我是 **Nexus**。"
    assert turn_result.message.additional_kwargs["reasoning_content"] == "用户问我是谁，这是一个简单问题。"


def test_run_agent_emits_hint_runtime_events_and_completion(monkeypatch):
    turn_stream_module, run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    history = DummyHistory()
    monkeypatch.setattr(run_loop_module, "get_session_history", lambda session_id: history)

    @tool
    def get_workflow_node_summary(node_id: str):
        """Return the selected node summary."""
        return '{"id":"node-1","type":"tool","name":"资产画像MCP调度","input_fields":[],"output_fields":[],"config_summary":{}}'

    monkeypatch.setattr(
        run_loop_module,
        "build_tool_catalog",
        lambda context, profile: _build_tool_catalog_stub(
            tools=[get_workflow_node_summary],
            workflow_tools=[get_workflow_node_summary],
        ),
    )
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (FakeLLM([AIMessage(content="你好")]), None, "glm-5"),
    )

    context = ChatRequestContext(
        user_prompt="讲讲这个节点",
        execution_hints=ExecutionHints(selected_nodes=["node-1"]),
        workflow_graph='{"nodes":[{"nodeId":"node-1","flowNodeType":"tool"}],"edges":[],"chatConfig":{}}',
        model_config_id=10003,
        session_id="s1",
    )

    events = asyncio.run(_collect(run_loop_module.run_agent(_build_runtime_config(context))))

    tool_selected_event = next(event for event in events if event.get("type") == "tool.selected")
    tool_completed_event = next(event for event in events if event.get("type") == "tool.completed")
    answer_done_event = next(event for event in events if event.get("type") == "answer.done")
    run_completed_event = next(event for event in events if event.get("type") == "run.completed")

    assert tool_selected_event["source"] == "hint"
    assert tool_selected_event["tool_name"] == "get_workflow_node_summary"
    assert tool_completed_event["source"] == "hint"
    assert "result" not in tool_completed_event
    assert answer_done_event["content"] == "你好"
    assert run_completed_event["final_answer_len"] == len("你好")
    assert history.user_messages == ["讲讲这个节点"]
    assert history.ai_messages == ["你好"]


def test_run_agent_raises_business_error_for_empty_answer(monkeypatch):
    turn_stream_module, run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    history = DummyHistory()
    monkeypatch.setattr(run_loop_module, "get_session_history", lambda session_id: history)
    monkeypatch.setattr(
        run_loop_module,
        "build_tool_catalog",
        lambda context, profile: _build_tool_catalog_stub(),
    )
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (FakeLLM([AIMessage(content="")]), None, "glm-5"),
    )

    context = ChatRequestContext(user_prompt="这个呢？", model_config_id=10003, session_id="s1")

    try:
        asyncio.run(_collect(run_loop_module.run_agent(_build_runtime_config(context))))
        raise AssertionError("expected BusinessError")
    except BusinessError as error:
        assert str(error) == "模型未返回有效回答"


def test_run_agent_stops_without_writing_history_when_cancelled(monkeypatch):
    turn_stream_module, run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    history = DummyHistory()
    cancellation_context = RunCancellationContext()
    monkeypatch.setattr(run_loop_module, "get_session_history", lambda session_id: history)
    monkeypatch.setattr(
        run_loop_module,
        "build_tool_catalog",
        lambda context, profile: _build_tool_catalog_stub(),
    )
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (
            CancelAfterFirstChunkLLM(cancellation_context),
            None,
            "glm-5",
        ),
    )

    context = ChatRequestContext(user_prompt="继续分析", model_config_id=10003, session_id="s1")

    try:
        asyncio.run(
            _collect(
                run_loop_module.run_agent(
                    _build_runtime_config(
                        context,
                        cancellation_context=cancellation_context,
                    )
                )
            )
        )
        raise AssertionError("expected RunCancelledError")
    except RunCancelledError:
        assert history.user_messages == []
        assert history.ai_messages == []


def test_select_tool_candidates_exposes_all_enabled_tools():
    _turn_stream_module, _run_loop_module, _chat_module, policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()

    tools = [
        SimpleNamespace(name="get_full_workflow_graph", description="完整工作流结构"),
        SimpleNamespace(name="load_skill", description="加载技能"),
        SimpleNamespace(name="get_current_time", description="当前时间"),
        SimpleNamespace(name="get_workflow_node_info", description="节点详情"),
    ]
    tool_catalog = _build_tool_catalog_stub(
        tools=tools,
        workflow_tools=[tools[0], tools[3]],
        skill_tools=[tools[1]],
        time_tools=[tools[2]],
    )

    candidates = policy_module.select_tool_candidates(tool_catalog)

    assert [tool.name for tool in candidates] == [
        "get_full_workflow_graph",
        "load_skill",
        "get_current_time",
        "get_workflow_node_info",
    ]


def test_select_tool_candidates_returns_empty_when_catalog_is_empty():
    _turn_stream_module, _run_loop_module, _chat_module, policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()

    assert policy_module.select_tool_candidates(_build_tool_catalog_stub()) == []


def test_resolve_tool_choice_returns_none_when_no_candidate_tools():
    _turn_stream_module, _run_loop_module, _chat_module, policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()

    result = policy_module.resolve_tool_choice(messages=[], candidate_tools=[])

    assert result == "none"


def test_resolve_tool_choice_returns_auto_when_tools_are_available():
    _turn_stream_module, _run_loop_module, _chat_module, policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    result = policy_module.resolve_tool_choice(
        messages=[],
        candidate_tools=[SimpleNamespace(name="get_full_workflow_graph")],
    )

    assert result == "auto"


def test_run_agent_resets_partial_answer_before_follow_up_tool_call(monkeypatch):
    turn_stream_module, run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    history = DummyHistory()
    monkeypatch.setattr(run_loop_module, "get_session_history", lambda session_id: history)

    @tool
    def lookup_detail(node_id: str):
        """Return detail for the requested node."""
        return '{"id":"node-1","tools":["a","b"]}'

    monkeypatch.setattr(
        run_loop_module,
        "build_tool_catalog",
        lambda context, profile: _build_tool_catalog_stub(
            tools=[lookup_detail],
            workflow_tools=[lookup_detail],
        ),
    )

    llm_rounds = iter(
        [
            FakeLLM(
                [
                    AIMessage(
                        content="先看看",
                        tool_calls=[{"name": "lookup_detail", "args": {"node_id": "node-1"}, "id": "call_1"}],
                    )
                ]
            ),
            FakeLLM([AIMessage(content="这个节点下有 2 个工具。")]),
        ]
    )
    monkeypatch.setattr(turn_stream_module, "get_llm", lambda *args, **kwargs: (next(llm_rounds), None, "glm-5"))

    context = ChatRequestContext(user_prompt="这个节点下有什么", model_config_id=10003, session_id="s1")
    events = asyncio.run(_collect(run_loop_module.run_agent(_build_runtime_config(context))))
    event_types = [event.get("type") for event in events]

    assert "answer.reset" in event_types
    assert event_types[-2:] == ["answer.done", "run.completed"]
    assert history.ai_messages == ["这个节点下有 2 个工具。"]


def test_run_agent_does_not_reset_answer_for_inline_thinking_response(monkeypatch):
    turn_stream_module, run_loop_module, _chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    history = DummyHistory()
    monkeypatch.setattr(run_loop_module, "get_session_history", lambda session_id: history)
    monkeypatch.setattr(
        run_loop_module,
        "build_tool_catalog",
        lambda context, profile: _build_tool_catalog_stub(),
    )
    monkeypatch.setattr(
        turn_stream_module,
        "get_llm",
        lambda *args, **kwargs: (
            FakeLLM(
                [
                    AIMessageChunk(content="<think>\n用户"),
                    AIMessageChunk(content="问我叫什么名字。\n</think>\n\n我是 **Nexus**。"),
                ]
            ),
            None,
            "minimax-m2.5",
        ),
    )

    context = ChatRequestContext(user_prompt="你叫什么名字？", model_config_id=10003, session_id="s1")
    events = asyncio.run(_collect(run_loop_module.run_agent(_build_runtime_config(context))))
    event_types = [event.get("type") for event in events]
    answer_deltas = [event["content"] for event in events if event.get("type") == "answer.delta"]
    thinking_deltas = [event["content"] for event in events if event.get("type") == "thinking.delta"]
    answer_done_event = next(event for event in events if event.get("type") == "answer.done")

    assert "answer.reset" not in event_types
    assert "".join(thinking_deltas) == "用户问我叫什么名字。"
    assert "".join(answer_deltas) == "我是 **Nexus**。"
    assert answer_done_event["content"] == "我是 **Nexus**。"
    assert history.ai_messages == ["我是 **Nexus**。"]


def test_chat_agent_delegates_to_shared_runtime(monkeypatch):
    _turn_stream_module, _run_loop_module, chat_module, _policy_module, _agent_service_module, _agent_api_module = _load_runtime_modules()
    monkeypatch.setattr(
        chat_module,
        "run_agent",
        lambda runtime_config: DummyChatAgent([{"type": "run.completed", "final_answer_len": 0}]).achat(runtime_config.context),
    )

    agent = chat_module.ChatAgent()
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")
    events = asyncio.run(_collect(agent.achat(context)))

    assert events == [{"type": "run.completed", "final_answer_len": 0}]


def test_agent_service_emits_error_and_done_for_business_error():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=ErrorChatAgent())
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")

    chunks = asyncio.run(_collect(service.handle_chat_request(context)))

    assert '"type": "error"' in chunks[-2]
    assert '"模型未返回有效回答"' in chunks[-2]
    assert chunks[-1] == agent_service_module.SSE_DONE


def test_agent_service_emits_only_done_for_cancelled_run():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=CancelledChatAgent())
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")

    chunks = asyncio.run(_collect(service.handle_chat_request(context)))

    assert chunks == [agent_service_module.SSE_DONE]


def test_agent_service_appends_done_after_run_completed():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(
        chat_agent=DummyChatAgent(
            [
                {"type": "run.started", "agent": "chat", "message": "开始处理用户问题"},
                {"type": "run.completed", "final_answer_len": 2, "message": "本轮处理完成"},
            ]
        )
    )
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")

    chunks = asyncio.run(_collect(service.handle_chat_request(context)))

    assert '"type": "run.completed"' in chunks[-2]
    assert chunks[-1] == agent_service_module.SSE_DONE


def test_safe_stream_completes_cleanly_with_disconnect_monitor():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, _agent_service_module, agent_api_module = _load_runtime_modules()

    class FakeRequest:
        async def is_disconnected(self):
            await asyncio.sleep(0)
            return False

    async def simple_stream():
        yield 'data: {"type":"run.completed"}\n\n'
        yield 'data: [DONE]\n\n'

    chunks = asyncio.run(
        _collect(
            agent_api_module._safe_stream(
                simple_stream(),
                "s1",
                request=FakeRequest(),
                cancellation_context=RunCancellationContext(),
            )
        )
    )

    assert chunks == [
        'data: {"type":"run.completed"}\n\n',
        'data: [DONE]\n\n',
    ]


def test_disabled_agent_request_emits_error_without_run_completed():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=DummyChatAgent([]))
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1", mode="builder")

    chunks = asyncio.run(_collect(service.handle_builder_request(context)))

    assert '"type": "run.started"' in chunks[0]
    assert '"type": "error"' in chunks[1]
    assert all('"type": "run.completed"' not in chunk for chunk in chunks)
    assert chunks[-1] == agent_service_module.SSE_DONE
