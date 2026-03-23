import asyncio
import importlib
import sys
import types
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class DummyStateGraph:
    def __init__(self, *args, **kwargs):
        self.nodes = {}
        self.edges = []
        self.conditional_edges = []
        self.entry_point = None

    def add_node(self, name, node):
        self.nodes[name] = node

    def set_entry_point(self, name):
        self.entry_point = name

    def add_edge(self, start, end):
        self.edges.append((start, end))

    def add_conditional_edges(self, start, router, mapping):
        self.conditional_edges.append((start, mapping))

    def compile(self):
        return self


def _install_langgraph_stubs() -> None:
    langgraph_module = types.ModuleType("langgraph")
    langgraph_module.__path__ = []

    graph_module = types.ModuleType("langgraph.graph")
    graph_message_module = types.ModuleType("langgraph.graph.message")
    prebuilt_module = types.ModuleType("langgraph.prebuilt")

    class DummyToolNode:
        def __init__(self, *args, **kwargs):
            pass

    graph_module.END = "END"
    graph_module.StateGraph = DummyStateGraph
    graph_message_module.add_messages = lambda left, right: (left or []) + (right or [])
    prebuilt_module.ToolNode = DummyToolNode

    langgraph_module.graph = graph_module
    langgraph_module.prebuilt = prebuilt_module

    sys.modules["langgraph"] = langgraph_module
    sys.modules["langgraph.graph"] = graph_module
    sys.modules["langgraph.graph.message"] = graph_message_module
    sys.modules["langgraph.prebuilt"] = prebuilt_module


def _load_chat_module():
    _install_langgraph_stubs()
    sys.modules.pop("nexus.agents.chat", None)
    return importlib.import_module("nexus.agents.chat")


class FakeLLM:
    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, messages):
        for chunk in self._chunks:
            yield chunk


async def _collect_events(async_iterable):
    events = []
    async for item in async_iterable:
        events.append(item)
    return events


def test_run_llm_answer_returns_text_directly(monkeypatch):
    chat_module = _load_chat_module()
    monkeypatch.setattr(chat_module, "get_llm", lambda *args, **kwargs: (FakeLLM([AIMessage(content="你好")]), None, "glm-5"))

    agent = chat_module.ChatAgent()
    state = {
        "messages": [SystemMessage(content="system"), HumanMessage(content="你好")],
    }
    context = chat_module.ChatRequestContext(user_prompt="你好", model_config_id=10003)

    result = asyncio.run(agent._run_llm_answer(state, context=context, config_id=10003, tools=[]))

    assert list(result.keys()) == ["messages"]
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "你好"
    assert result["messages"][0].tool_calls == []


def test_selected_node_still_goes_through_model_tool_selection(monkeypatch):
    chat_module = _load_chat_module()
    llm_called = {"count": 0}

    def fake_get_llm(*args, **kwargs):
        llm_called["count"] += 1
        return (
            FakeLLM(
                [
                    AIMessage(
                        content="",
                        tool_calls=[{"name": "get_workflow_node_info", "args": {"node_id": "kIL7EmgolxCm"}, "id": "call_1", "type": "tool_call"}],
                    )
                ]
            ),
            None,
            "glm-5",
        )

    monkeypatch.setattr(chat_module, "get_llm", fake_get_llm)

    agent = chat_module.ChatAgent()
    state = {
        "messages": [SystemMessage(content="system"), HumanMessage(content="selected_node(kIL7EmgolxCm) 这个做了什么？")],
    }
    context = chat_module.ChatRequestContext(
        user_prompt="selected_node(kIL7EmgolxCm) 这个做了什么？",
        model_config_id=10003,
    )

    result = asyncio.run(agent._run_llm_answer(state, context=context, config_id=10003, tools=[]))

    assert llm_called["count"] == 1
    assert len(result["messages"]) == 1
    assert result["messages"][0].tool_calls[0]["name"] == "get_workflow_node_info"


def test_build_app_has_only_generation_and_tool_nodes(monkeypatch):
    chat_module = _load_chat_module()

    monkeypatch.setattr(chat_module, "build_workflow_tools", lambda context: ([], object()))
    monkeypatch.setattr(chat_module, "build_skill_tools", lambda context: ([], object()))
    monkeypatch.setattr(chat_module, "build_time_tools", lambda context: ([], object()))

    class DummyToolExecutionManager:
        def __init__(self, tools):
            self.tools = tools

        def build_execution_node(self):
            return object()

    monkeypatch.setattr(chat_module, "ToolExecutionManager", DummyToolExecutionManager)

    agent = chat_module.ChatAgent()
    context = chat_module.ChatRequestContext(user_prompt="你好", model_config_id=10003)
    app = agent._build_app(context)

    assert chat_module.NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT in app.nodes
    assert chat_module.NODE_EXECUTE_MODEL_REQUESTED_TOOLS in app.nodes
    assert len(app.nodes) == 2
    assert app.entry_point == chat_module.NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT
    assert app.edges == [
        (
            chat_module.NODE_EXECUTE_MODEL_REQUESTED_TOOLS,
            chat_module.NODE_GENERATE_RESPONSE_WITH_TOOL_CONTEXT,
        )
    ]


def test_achat_emits_runtime_events_without_extra_phase(monkeypatch):
    chat_module = _load_chat_module()

    class DummyHistory:
        def __init__(self):
            self.messages = []
            self.user_messages = []
            self.ai_messages = []

        def add_user_message(self, message):
            self.user_messages.append(message)

        def add_ai_message(self, message):
            self.ai_messages.append(message)

    history = DummyHistory()
    monkeypatch.setattr(chat_module, "get_session_history", lambda session_id: history)

    class FakeApp:
        async def astream(self, state, stream_mode=None):
            yield ("custom", {"event": "token", "text": "你好"})
            yield ("values", {"messages": [*state["messages"], AIMessage(content="你好")]})

    agent = chat_module.ChatAgent()
    monkeypatch.setattr(agent, "_build_app", lambda context: FakeApp())

    context = chat_module.ChatRequestContext(user_prompt="你好", model_config_id=10003, session_id="s1")
    events = asyncio.run(_collect_events(agent.achat(context)))

    event_types = [event.get("type") for event in events if isinstance(event, dict)]
    event_phases = [event.get("phase") for event in events if isinstance(event, dict)]

    assert "phase.started" in event_types
    assert "phase.completed" in event_types
    assert set(phase for phase in event_phases if phase) <= {"analyze_question", "generate_final_answer"}
    assert history.user_messages == ["你好"]
    assert history.ai_messages == ["你好"]
