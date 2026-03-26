import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nexus.common.exceptions import BusinessError
from nexus.core.agent_runtime import active_run_registry
from nexus.core.agent_runtime.cancellation import (
    RunCancellationContext,
    RunCancelledError,
    await_with_cancellation,
)
from nexus.core.agent_runtime.contracts import AgentRuntimeConfig
from nexus.core.schemas import ChatCancelRequest, ChatRequestContext, ExecutionHints
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


def _load_stream_session_module():
    return _reload_module("nexus.api.streaming.session")


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

    def add_messages(self, messages):
        for message in messages:
            self.messages.append(message)
            if isinstance(message, HumanMessage):
                self.user_messages.append(message.content)
            elif isinstance(message, AIMessage):
                self.ai_messages.append(message.content)

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
        assert "模型输出超时：首Token返回过慢" in str(error)


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

    events = asyncio.run(_collect(service.handle_chat_request(context)))

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "模型未返回有效回答" in events[0]["message"]


def test_agent_service_emits_only_done_for_cancelled_run():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=CancelledChatAgent())
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")

    events = asyncio.run(_collect(service.handle_chat_request(context)))

    assert events == []


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

    events = asyncio.run(_collect(service.handle_chat_request(context)))

    assert [event["type"] for event in events] == ["run.started", "run.completed"]


def test_safe_stream_completes_cleanly_with_disconnect_monitor():
    stream_session_module = _load_stream_session_module()

    class FakeRequest:
        async def is_disconnected(self):
            await asyncio.sleep(0)
            return False

    async def simple_stream():
        yield {"type": "run.completed"}

    chunks = asyncio.run(
        _collect(
            stream_session_module.safe_stream(
                simple_stream(),
                "s1",
                request=FakeRequest(),
                cancellation_context=RunCancellationContext(),
            )
        )
    )

    assert len(chunks) == 1
    assert json.loads(chunks[0]["data"])["type"] == "run.completed"


def test_safe_stream_fails_when_terminal_event_missing(monkeypatch):
    stream_session_module = _load_stream_session_module()
    captured_status = {}

    async def fake_mark_finished(*, session_id, request_id, status):
        captured_status["session_id"] = session_id
        captured_status["request_id"] = request_id
        captured_status["status"] = status

    monkeypatch.setattr(stream_session_module.active_run_registry, "mark_finished", fake_mark_finished)

    async def non_terminal_stream():
        yield {"type": "answer.delta", "content": "partial"}

    chunks = asyncio.run(
        _collect(
            stream_session_module.safe_stream(
                non_terminal_stream(),
                "s1",
                request_id="r_missing_terminal",
            )
        )
    )

    payloads = [json.loads(chunk["data"]) for chunk in chunks]
    assert [payload["type"] for payload in payloads] == ["answer.delta", "error"]
    assert "终态事件" in payloads[-1]["message"]
    assert captured_status == {"session_id": "s1", "request_id": "r_missing_terminal", "status": "failed"}


def test_safe_stream_keeps_completed_status_when_exception_after_terminal(monkeypatch):
    stream_session_module = _load_stream_session_module()
    captured_status = {}

    async def fake_mark_finished(*, session_id, request_id, status):
        captured_status["session_id"] = session_id
        captured_status["request_id"] = request_id
        captured_status["status"] = status

    monkeypatch.setattr(stream_session_module.active_run_registry, "mark_finished", fake_mark_finished)

    async def terminal_then_error_stream():
        yield {"type": "run.completed"}
        raise RuntimeError("write failed after terminal")

    chunks = asyncio.run(
        _collect(
            stream_session_module.safe_stream(
                terminal_then_error_stream(),
                "s1",
                request_id="r_terminal_then_error",
            )
        )
    )

    payloads = [json.loads(chunk["data"]) for chunk in chunks]
    assert [payload["type"] for payload in payloads] == ["run.completed"]
    assert captured_status == {"session_id": "s1", "request_id": "r_terminal_then_error", "status": "completed"}


def test_safe_stream_marks_cancelled_status_for_cancelled_chat_run(monkeypatch):
    stream_session_module = _load_stream_session_module()
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=CancelledChatAgent())
    context = ChatRequestContext(
        user_prompt="你好",
        model_config_id=10003,
        session_id="s1",
        request_id="r_stream_cancel",
    )
    cancellation_context = RunCancellationContext()
    captured_status = {}

    async def fake_mark_finished(*, session_id, request_id, status):
        captured_status["session_id"] = session_id
        captured_status["request_id"] = request_id
        captured_status["status"] = status

    monkeypatch.setattr(stream_session_module.active_run_registry, "mark_finished", fake_mark_finished)

    chunks = asyncio.run(
        _collect(
            stream_session_module.safe_stream(
                service.handle_chat_request_with_cancellation(
                    context,
                    cancellation_context=cancellation_context,
                ),
                context.session_id,
                request_id=context.request_id,
                cancellation_context=cancellation_context,
            )
        )
    )

    assert chunks == []
    assert captured_status == {"session_id": "s1", "request_id": "r_stream_cancel", "status": "cancelled"}


def test_disabled_agent_request_emits_error_without_run_completed():
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, agent_service_module, _agent_api_module = _load_runtime_modules()
    service = agent_service_module.AgentService(chat_agent=DummyChatAgent([]))
    context = ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1", mode="builder")

    events = asyncio.run(_collect(service.handle_builder_request(context)))

    assert [event["type"] for event in events] == ["run.started", "error"]


def test_active_run_registry_can_cancel_registered_request():
    cancellation_context = RunCancellationContext()

    async def _run():
        await active_run_registry.register(
            session_id="s1",
            request_id="r_registry_cancel",
            cancellation_context=cancellation_context,
        )
        cancel_result = await active_run_registry.cancel(
            session_id="s1",
            request_id="r_registry_cancel",
            reason="用户主动停止生成",
        )
        await active_run_registry.mark_finished(
            session_id="s1",
            request_id="r_registry_cancel",
            status="cancelled",
        )
        return cancel_result

    cancelled = asyncio.run(_run())

    assert cancelled.status == "accepted"
    assert cancelled.accepted is True
    assert cancellation_context.is_cancelled is True
    assert cancellation_context.reason == "用户主动停止生成"


def test_active_run_registry_reuse_request_id_after_finish_is_allowed():
    first_context = RunCancellationContext()
    second_context = RunCancellationContext()

    async def _run():
        request_id = "r_reuse"
        await active_run_registry.register(
            session_id="s1",
            request_id=request_id,
            cancellation_context=first_context,
        )
        await active_run_registry.mark_finished(
            session_id="s1",
            request_id=request_id,
            status="completed",
        )
        await active_run_registry.register(
            session_id="s1",
            request_id=request_id,
            cancellation_context=second_context,
        )
        return await active_run_registry.cancel(
            session_id="s1",
            request_id=request_id,
            reason="用户主动停止生成",
        )

    cancelled = asyncio.run(_run())

    assert cancelled.status == "accepted"
    assert cancelled.accepted is True
    assert second_context.is_cancelled is True


def test_active_run_registry_same_request_id_isolated_by_session():
    context_s1 = RunCancellationContext()
    context_s2 = RunCancellationContext()

    async def _run():
        request_id = "r_same"
        await active_run_registry.register(
            session_id="s1",
            request_id=request_id,
            cancellation_context=context_s1,
        )
        await active_run_registry.mark_finished(
            session_id="s1",
            request_id=request_id,
            status="completed",
        )
        await active_run_registry.register(
            session_id="s2",
            request_id=request_id,
            cancellation_context=context_s2,
        )
        return await active_run_registry.cancel(
            session_id="s2",
            request_id=request_id,
            reason="用户主动停止生成",
        )

    cancelled = asyncio.run(_run())

    assert cancelled.status == "accepted"
    assert cancelled.accepted is True
    assert context_s2.is_cancelled is True


def test_cancel_chat_completion_endpoint_marks_run_cancelled(monkeypatch):
    _turn_stream_module, _run_loop_module, _chat_module, _policy_module, _agent_service_module, agent_api_module = _load_runtime_modules()
    cancellation_context = RunCancellationContext()
    monkeypatch.setattr(agent_api_module, "check_login", lambda _token: True)

    class FakeRequest:
        headers = {"Authorization": "Bearer token"}

    async def _run():
        request_id = "r_cancel_endpoint"
        await agent_api_module.active_run_registry.register(
            session_id="s1",
            request_id=request_id,
            cancellation_context=cancellation_context,
        )
        cancel_task = asyncio.create_task(
            agent_api_module.cancel_chat_completion(
                ChatCancelRequest(session_id="s1", request_id=request_id),
                FakeRequest(),
            )
        )
        while not cancellation_context.is_cancelled and not cancel_task.done():
            await asyncio.sleep(0)
        if cancellation_context.is_cancelled:
            await agent_api_module.active_run_registry.mark_finished(
                session_id="s1",
                request_id=request_id,
                status="cancelled",
            )
        return await cancel_task

    payload = asyncio.run(_run())

    assert payload["code"] == 200
    assert payload["data"]["accepted"] is True
    assert payload["data"]["cancelled"] is True
    assert payload["data"]["status"] == "accepted"
    assert cancellation_context.is_cancelled is True


def test_await_with_cancellation_runs_cancel_action_and_raises_cancelled():
    cancellation_context = RunCancellationContext()
    cancel_action_called = []

    async def never_finishes():
        await asyncio.Future()

    async def cancel_action():
        cancel_action_called.append(True)

    async def _run():
        task = asyncio.create_task(
            await_with_cancellation(
                never_finishes(),
                cancellation_context=cancellation_context,
                cancel_action=cancel_action,
                operation_name="unit-test-operation",
            )
        )
        await asyncio.sleep(0)
        cancellation_context.cancel("用户主动停止生成")
        await task

    try:
        asyncio.run(_run())
        raise AssertionError("expected RunCancelledError")
    except RunCancelledError as error:
        assert str(error) == "用户主动停止生成"
    assert cancel_action_called == [True]
