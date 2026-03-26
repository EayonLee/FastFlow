"""
统一缓存管理器（基于 functools.lru_cache）。

本模块统一管理两类进程内缓存：
1) `session_history`（短期会话记忆）
2) `llm_runtime`（模型运行时实例）

缓存使用方（便于维护排查）：
- `session_history`
  - 读取入口：`nexus/core/history/manager.py:get_session_history`
  - 主要使用：`nexus/agents/chat.py`（组装历史消息、请求结束后写回整轮 user/ai 消息）
- `llm_runtime`
  - 读取/写入：`nexus/core/llm/factory.py`（按 model_config_id 复用模型实例）

`session_history` 策略：
- 缓存键：`session_id`
- `session_id` 数量不设上限（进程重启前持续可用）
- 单会话轮数上限：由 `SESSION_HISTORY_MAX_TURNS` 控制（默认 10 轮）
- 仅保留完整轮次：`HumanMessage -> AIMessage`
- 自动剔除 `ToolMessage`、`SystemMessage`、thinking 相关载荷与其他异常消息
- 时间过期：由 `SESSION_HISTORY_EXPIRE_SECONDS` 控制，<=0 时不过期

为什么没有 `set_session_history`：
- `get_session_history` 返回的是可变历史对象本身（同一 `session_id` 对应同一实例）。
- 调用方直接执行 `add_messages` 即完成“原地写入”。
- 因此不需要额外 `set_*` 回写接口。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from threading import RLock
from time import monotonic
from typing import Any

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import PrivateAttr

from nexus.config.config import get_config

_settings = get_config()
SESSION_HISTORY_MAX_TURNS = max(1, int(_settings.SESSION_HISTORY_MAX_TURNS))
# <= 0 代表不过期。
SESSION_HISTORY_EXPIRE_SECONDS = int(_settings.SESSION_HISTORY_EXPIRE_SECONDS)

_SESSION_HISTORY_LOCK = RLock()
_LLM_RUNTIME_LOCK = RLock()


def _normalize_human_message(message: HumanMessage) -> HumanMessage | None:
    content = str(message.content or "")
    if not content.strip():
        return None
    return HumanMessage(content=content)


def _normalize_ai_message(message: AIMessage) -> AIMessage | None:
    content = str(message.content or "")
    if not content.strip():
        return None
    return AIMessage(content=content)


def _select_latest_complete_turn_messages(messages: list[BaseMessage], max_turns: int) -> list[BaseMessage]:
    """
    从任意消息序列中提取最近 N 个完整轮次。

    规则：
    - 只识别 `HumanMessage -> AIMessage` 这一种合法轮次；
    - 非 Human/AI 消息全部丢弃；
    - 连续多个 Human 时，仅保留最后一个等待配对；
    - 没有配对成功的尾部残缺消息会被丢弃；
    - 返回值中的消息会被标准化为仅包含 `content` 的 Human/AI 消息。
    """
    normalized_turns: list[tuple[HumanMessage, AIMessage]] = []
    pending_human: HumanMessage | None = None

    for message in messages:
        if isinstance(message, HumanMessage):
            pending_human = _normalize_human_message(message)
            continue

        if isinstance(message, AIMessage):
            if pending_human is None:
                continue
            normalized_ai = _normalize_ai_message(message)
            if normalized_ai is None:
                continue
            normalized_turns.append((pending_human, normalized_ai))
            pending_human = None

    latest_turns = normalized_turns[-max(1, int(max_turns)) :]
    flattened_messages: list[BaseMessage] = []
    for human_message, ai_message in latest_turns:
        flattened_messages.extend((human_message, ai_message))
    return flattened_messages


class BoundedTurnChatMessageHistory(ChatMessageHistory):
    """
    带轮数上限的会话历史。

    历史内部只保留完整轮次：
    - 一个 `HumanMessage`
    - 紧接着一个 `AIMessage`

    其他类型消息与不完整轮次均不会进入 `messages`。
    """

    _max_turns: int = PrivateAttr()
    _pending_human: HumanMessage | None = PrivateAttr(default=None)

    def __init__(self, max_turns: int):
        super().__init__()
        self._max_turns = max(1, int(max_turns))
        self._pending_human = None

    def _trim_to_latest_turns(self) -> None:
        self.messages = _select_latest_complete_turn_messages(self.messages, self._max_turns)

    def add_message(self, message: BaseMessage) -> None:
        if isinstance(message, HumanMessage):
            self._pending_human = _normalize_human_message(message)
            return

        if not isinstance(message, AIMessage) or self._pending_human is None:
            return

        normalized_ai = _normalize_ai_message(message)
        if normalized_ai is None:
            return

        self.messages.extend([self._pending_human, normalized_ai])
        self._pending_human = None
        self._trim_to_latest_turns()

    def add_messages(self, messages: list[BaseMessage]) -> None:
        for message in messages:
            self.add_message(message)

    def clear(self) -> None:
        super().clear()
        self._pending_human = None


@dataclass
class SessionHistorySlot:
    # 单个 session_id 对应一个可变历史对象；调用方通过 add_messages 原地更新。
    history: BaseChatMessageHistory = field(default_factory=lambda: BoundedTurnChatMessageHistory(SESSION_HISTORY_MAX_TURNS))
    updated_at: float = 0.0

    def reset(self) -> None:
        self.history = BoundedTurnChatMessageHistory(SESSION_HISTORY_MAX_TURNS)
        self.updated_at = 0.0


@dataclass
class LLMRuntimeSlot:
    # 按 model_config_id 缓存模型运行时（适配器 + 实例等）。
    runtime: Any = None


def _trim_history_messages_in_place(history: BaseChatMessageHistory, max_turns: int) -> None:
    """
    对任意 BaseChatMessageHistory 做兜底裁剪。

    作用：
    - 兼容非 `BoundedTurnChatMessageHistory` 的历史对象；
    - 保证无论历史对象具体实现如何，对外都满足“最多 N 个完整轮次”。
    """
    messages = getattr(history, "messages", None)
    if not isinstance(messages, list):
        return
    history.messages = _select_latest_complete_turn_messages(messages, max_turns)
    if isinstance(history, BoundedTurnChatMessageHistory):
        history._pending_human = None


def _is_session_history_expired(updated_at: float) -> bool:
    """
    会话历史过期判定。

    - `SESSION_HISTORY_EXPIRE_SECONDS <= 0` 时，视为永不过期。
    - 否则按惰性 TTL（访问时检查）判定是否过期。
    """
    if SESSION_HISTORY_EXPIRE_SECONDS <= 0:
        return False
    if updated_at <= 0:
        return True
    return (monotonic() - updated_at) >= SESSION_HISTORY_EXPIRE_SECONDS


@lru_cache(maxsize=None)
def _session_history_slot(session_id: str) -> SessionHistorySlot:
    """
    session_history 槽位工厂（无限容量）。
    """
    return SessionHistorySlot()


@lru_cache(maxsize=None)
def _llm_runtime_slot(model_config_id: str) -> LLMRuntimeSlot:
    """llm_runtime 槽位工厂（无限容量）。"""
    return LLMRuntimeSlot()


class CacheManager:
    """
    Nexus 统一缓存管理器（进程内）。
    """

    @staticmethod
    def get_llm_runtime(model_config_id: str) -> Any:
        """
        读取 LLM 运行时缓存。

        使用方：`nexus/core/llm/factory.py`。
        """
        if not model_config_id:
            return None
        with _LLM_RUNTIME_LOCK:
            return _llm_runtime_slot(model_config_id).runtime

    @staticmethod
    def set_llm_runtime(model_config_id: str, runtime: Any) -> None:
        """
        写入 LLM 运行时缓存。

        使用方：`nexus/core/llm/factory.py`。
        """
        if not model_config_id:
            return
        with _LLM_RUNTIME_LOCK:
            _llm_runtime_slot(model_config_id).runtime = runtime

    @staticmethod
    def get_session_history(session_id: str) -> BaseChatMessageHistory:
        """
        获取指定 session_id 的短期会话历史对象。

        行为说明：
        - 若该 session 首次访问：创建新历史对象；
        - 若会话已过期：重置历史对象；
        - 返回同一对象引用，调用方可直接 add 消息，无需 set 回写；
        - 历史对象内部只保留最近 N 个完整轮次（N 由配置项控制）。
        """
        normalized_session_id = str(session_id or "").strip()
        with _SESSION_HISTORY_LOCK:
            slot = _session_history_slot(normalized_session_id)
            if _is_session_history_expired(slot.updated_at):
                slot.reset()
            _trim_history_messages_in_place(slot.history, SESSION_HISTORY_MAX_TURNS)
            slot.updated_at = monotonic()
            return slot.history
