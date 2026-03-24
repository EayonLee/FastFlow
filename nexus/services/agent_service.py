import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict

from nexus.agents.chat import ChatAgent
from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.agent_runtime import RunCancellationContext, RunCancelledError
from nexus.core.event import build_run_started_event
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)
SSE_DONE = "data: [DONE]\n\n"


def _to_sse(payload: Dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class AgentService:
    """
    智能体服务层。

    这里只负责两件事：
    1. 给业务事件补齐 SSE 元数据。
    2. 在业务流结束后补发传输层的 `[DONE]` 哨兵。
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
    ) -> AsyncGenerator[str, None]:
        """
        统一处理当前被禁用的智能体入口，保持固定的 SSE 事件顺序。
        """
        event_seq = 1
        yield _to_sse(
            self._enrich_event(
                build_run_started_event(agent=agent),
                session_id=session_id,
                seq=event_seq,
            )
        )
        event_seq += 1
        logger.info("%s agent is disabled.", agent.capitalize())
        yield _to_sse(
            self._enrich_event(
                {"type": "error", "message": message},
                session_id=session_id,
                seq=event_seq,
            )
        )
        yield SSE_DONE

    async def handle_chat_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理对话型智能体请求。

        约定：
        - `ChatAgent` 负责产出业务事件，如 `answer.delta` / `run.completed`
        - `AgentService` 只负责把这些事件编码成 SSE，并在末尾补一个 `[DONE]`
        """
        cancellation_context = RunCancellationContext()
        async for event in self.handle_chat_request_with_cancellation(
            context,
            cancellation_context=cancellation_context,
        ):
            yield event

    async def handle_chat_request_with_cancellation(
        self,
        context: ChatRequestContext,
        *,
        cancellation_context: RunCancellationContext,
    ) -> AsyncGenerator[str, None]:
        """处理带取消上下文的 chat 请求。"""
        event_seq = 1
        try:
            async for event in self.chat_agent.achat(
                context,
                cancellation_context=cancellation_context,
            ):
                if not isinstance(event, dict):
                    raise TypeError(f"invalid agent event type: {type(event)}")
                yield _to_sse(
                    self._enrich_event(event, session_id=context.session_id or "", seq=event_seq)
                )
                event_seq += 1
        except RunCancelledError:
            logger.info(
                "[SSE 会话取消] agent=chat session_id=%s reason=%s",
                context.session_id or "",
                cancellation_context.reason,
            )
        except BusinessError as e:
            logger.error("ChatAgent error: %s", e)
            yield _to_sse(
                self._enrich_event(
                    {"type": "error", "message": e.message},
                    session_id=context.session_id or "",
                    seq=event_seq,
                )
            )
        except Exception as e:
            logger.error("ChatAgent error. user_prompt=%s error=%s", context.user_prompt, e)
            yield _to_sse(
                self._enrich_event(
                    {"type": "error", "message": str(e)},
                    session_id=context.session_id or "",
                    seq=event_seq,
                )
            )

        # `[DONE]` 只表示 SSE 传输结束，不承担业务成功语义。
        logger.info("[SSE 会话完成] agent=chat session_id=%s", context.session_id or "")
        yield SSE_DONE

    async def handle_builder_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理构建型智能体请求（保留入口，内部逻辑已清空）。
        """
        async for chunk in self._handle_disabled_agent_request(
            agent="builder",
            message="Builder 智能体暂未开放 🚧，相关能力正在完善中，敬请期待 ✨",
            session_id=context.session_id or "",
        ):
            yield chunk

    async def handle_debugger_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理 Debugger 智能体请求（保留入口，内部逻辑已清空）。
        """
        async for chunk in self._handle_disabled_agent_request(
            agent="debug",
            message="SOLO Debugger 智能体暂未开放 🛠️，调试能力正在完善中，敬请期待 ✨",
            session_id=context.session_id or "",
        ):
            yield chunk
