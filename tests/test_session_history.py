import sys
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nexus.core.cache import manager as cache_manager_module


def _contents(messages):
    return [message.content for message in messages]


def test_bounded_turn_history_keeps_latest_complete_turns():
    history = cache_manager_module.BoundedTurnChatMessageHistory(max_turns=10)

    for index in range(1, 12):
        history.add_messages(
            [
                HumanMessage(content=f"user-{index}"),
                AIMessage(content=f"ai-{index}"),
            ]
        )

    assert len(history.messages) == 20
    assert _contents(history.messages[:2]) == ["user-2", "ai-2"]
    assert _contents(history.messages[-2:]) == ["user-11", "ai-11"]


def test_get_session_history_cleans_non_turn_messages_and_thinking_payloads():
    cache_manager_module._session_history_slot.cache_clear()

    slot = cache_manager_module._session_history_slot("mixed-session")
    slot.history.messages = [
        SystemMessage(content="system"),
        HumanMessage(content="user-1"),
        ToolMessage(content="tool", tool_call_id="call-1", name="lookup"),
        AIMessage(content="ai-1", additional_kwargs={"reasoning_content": "hidden thinking"}),
        HumanMessage(content="user-2"),
    ]
    slot.updated_at = cache_manager_module.monotonic()

    history = cache_manager_module.CacheManager.get_session_history("mixed-session")

    assert _contents(history.messages) == ["user-1", "ai-1"]
    assert all(isinstance(message, (HumanMessage, AIMessage)) for message in history.messages)
    assert history.messages[1].additional_kwargs == {}


def test_bounded_turn_history_discards_incomplete_tail_and_malformed_prefix():
    history = cache_manager_module.BoundedTurnChatMessageHistory(max_turns=10)
    history.add_messages(
        [
            AIMessage(content="stray-ai"),
            HumanMessage(content="user-1"),
            HumanMessage(content="user-2"),
            AIMessage(content="ai-2"),
            HumanMessage(content="user-3"),
        ]
    )

    assert _contents(history.messages) == ["user-2", "ai-2"]


def test_cache_manager_resets_expired_history_and_still_trims_by_turn():
    cache_manager_module._session_history_slot.cache_clear()

    original_expire_seconds = cache_manager_module.SESSION_HISTORY_EXPIRE_SECONDS
    try:
        cache_manager_module.SESSION_HISTORY_EXPIRE_SECONDS = 1
        first_history = cache_manager_module.CacheManager.get_session_history("expired-session")
        first_history.add_messages([HumanMessage(content="user-1"), AIMessage(content="ai-1")])

        slot = cache_manager_module._session_history_slot("expired-session")
        slot.updated_at = 0.0

        history = cache_manager_module.CacheManager.get_session_history("expired-session")
        assert history is not first_history
        assert history.messages == []

        for index in range(1, 12):
            history.add_messages(
                [
                    HumanMessage(content=f"user-{index}"),
                    AIMessage(content=f"ai-{index}"),
                ]
            )

        assert len(history.messages) == 20
        assert _contents(history.messages[:2]) == ["user-2", "ai-2"]
        assert _contents(history.messages[-2:]) == ["user-11", "ai-11"]
    finally:
        cache_manager_module.SESSION_HISTORY_EXPIRE_SECONDS = original_expire_seconds
        cache_manager_module._session_history_slot.cache_clear()
