import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict

from nexus.agents.chat import ChatAgent
from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.event import build_run_completed_event, build_run_started_event
from nexus.core.schemas import ChatRequestContext

logger = get_logger(__name__)
SSE_DONE = "data: [DONE]\n\n"


def _to_sse(payload: Dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


class AgentService:
    """
    智能体服务层
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

    async def handle_chat_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """处理对话型智能体请求。"""
        event_seq = 1
        try:
            async for event in self.chat_agent.achat(context):
                if not isinstance(event, dict):
                    raise TypeError(f"invalid agent event type: {type(event)}")
                yield _to_sse(
                    self._enrich_event(event, session_id=context.session_id or "", seq=event_seq)
                )
                event_seq += 1
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

        yield SSE_DONE

    async def handle_builder_request(self, context: ChatRequestContext) -> AsyncGenerator[str, None]:
        """
        处理构建型智能体请求（保留入口，内部逻辑已清空）。
        """
        event_seq = 1
        session_id = context.session_id or ""
        yield _to_sse(
            self._enrich_event(
                build_run_started_event(agent="builder"),
                session_id=session_id,
                seq=event_seq,
            )
        )
        event_seq += 1
        logger.info("BuilderAgent is disabled.")
        yield _to_sse(
            self._enrich_event(
                {"type": "error", "message": "Builder agent is temporarily disabled"},
                session_id=session_id,
                seq=event_seq,
            )
        )
        event_seq += 1
        yield _to_sse(
            self._enrich_event(
                build_run_completed_event(final_answer_len=0),
                session_id=session_id,
                seq=event_seq,
            )
        )
        yield SSE_DONE
