from __future__ import annotations

from typing import Any, AsyncGenerator

from nexus.core.agent_runtime import AgentRuntimeConfig, RunCancellationContext, run_agent
from nexus.core.prompts.chat_prompts import CHAT_SYSTEM_PROMPT
from nexus.core.schemas import ChatRequestContext
from nexus.core.tools.runtime.contracts import CHAT_AGENT_TOOL_PROFILE


class ChatAgent:
    """
    ChatAgent 只负责提供 chat 运行配置。

    共享的 turn streaming、工具循环和收尾协议都下沉到 `nexus.core.agent_runtime`。
    """

    def _build_runtime_config(
        self,
        context: ChatRequestContext,
        cancellation_context: RunCancellationContext | None = None,
    ) -> AgentRuntimeConfig:
        """将 chat 的固定策略包装成共享 runtime 可消费的配置对象。"""
        return AgentRuntimeConfig(
            agent_name="chat",
            context=context,
            system_prompt=CHAT_SYSTEM_PROMPT,
            tool_profile=CHAT_AGENT_TOOL_PROFILE,
            supports_workflow_context=True,
            cancellation_context=cancellation_context,
        )

    async def achat(
        self,
        context: ChatRequestContext,
        cancellation_context: RunCancellationContext | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """将 chat 请求委托给共享 runtime，并透传统一事件流。"""
        async for event in run_agent(self._build_runtime_config(context, cancellation_context)):
            yield event
