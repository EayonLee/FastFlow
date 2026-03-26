from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict

from nexus.agents.chat import ChatAgent
from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.agent_runtime import RunCancellationContext, RunCancelledError
from nexus.core.event import build_run_started_event
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)


class AgentService:
    """
    智能体服务层。

    这里只负责一件事：给业务事件补齐 SSE 元数据。

    传输层编码（SSE 行协议、ping、连接关闭）统一由 `EventSourceResponse` 负责。
    """

    def __init__(self, chat_agent: ChatAgent):
        self.chat_agent = chat_agent

    @staticmethod
    def _enrich_event(event: Dict[str, Any], *, session_id: str, seq: int) -> Dict[str, Any]:
        payload = dict(event)
        payload["session_id"] = session_id
        payload["seq"] = seq
        payload["ts"] = datetime.now(timezone.utc).isoformat()
        return payload

    async def _handle_disabled_agent_request(
        self,
        *,
        agent: str,
        message: str,
        session_id: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        统一处理当前被禁用的智能体入口，保持固定的 SSE 事件顺序。
        """
        event_seq = 1
        yield self._enrich_event(
            build_run_started_event(agent=agent),
            session_id=session_id,
            seq=event_seq,
        )
        event_seq += 1
        logger.info("%s agent is disabled.", agent.capitalize())
        yield self._enrich_event(
            {"type": "error", "message": message},
            session_id=session_id,
            seq=event_seq,
        )

    async def handle_chat_request(self, context: ChatRequestContext) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理对话型智能体请求。

        约定：
        - `ChatAgent` 负责产出业务事件，如 `answer.delta` / `run.completed`
        - `AgentService` 只负责补齐元数据，不做传输层编码
        """
        cancellation_context = RunCancellationContext()
        try:
            async for event in self.handle_chat_request_with_cancellation(
                context,
                cancellation_context=cancellation_context,
            ):
                yield event
        except RunCancelledError:
            logger.info(
                "[SSE 会话取消] agent=chat session_id=%s request_id=%s reason=%s",
                context.session_id or "",
                context.request_id or "",
                cancellation_context.reason,
            )
            return

    async def handle_chat_request_with_cancellation(
        self,
        context: ChatRequestContext,
        *,
        cancellation_context: RunCancellationContext,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理带取消上下文的 chat 请求。"""
        event_seq = 1
        try:
            async for event in self.chat_agent.achat(
                context,
                cancellation_context=cancellation_context,
            ):
                if not isinstance(event, dict):
                    raise TypeError(f"invalid agent event type: {type(event)}")
                yield self._enrich_event(event, session_id=context.session_id or "", seq=event_seq)
                event_seq += 1
        except RunCancelledError:
            logger.info(
                "[SSE 会话取消] agent=chat session_id=%s request_id=%s reason=%s",
                context.session_id or "",
                context.request_id or "",
                cancellation_context.reason,
            )
            raise
        except BusinessError as e:
            logger.error("ChatAgent error: %s", e)
            yield self._enrich_event(
                {"type": "error", "message": e.message},
                session_id=context.session_id or "",
                seq=event_seq,
            )
        except Exception as e:
            logger.error("ChatAgent error. user_prompt=%s error=%s", context.user_prompt, e)
            yield self._enrich_event(
                {"type": "error", "message": str(e)},
                session_id=context.session_id or "",
                seq=event_seq,
            )

    async def handle_builder_request(self, context: ChatRequestContext) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理构建型智能体请求（保留入口，内部逻辑已清空）。
        """
        async for event in self._handle_disabled_agent_request(
            agent="builder",
            message="SOLO Builder 智能体暂未开放 🚧，相关能力正在完善中，敬请期待 ✨",
            session_id=context.session_id or "",
        ):
            yield event

    async def handle_debugger_request(self, context: ChatRequestContext) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理 Debugger 智能体请求（保留入口，内部逻辑已清空）。
        """
        async for event in self._handle_disabled_agent_request(
            agent="debugger",
            message="SOLO Debugger 智能体暂未开放 🛠️，相关能力正在完善中，敬请期待 ✨",
            session_id=context.session_id or "",
        ):
            yield event
