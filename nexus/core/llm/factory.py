from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.llm.litellm_adapter import LiteLLMAdapter
from nexus.core.llm.tool_call_adapter import ToolCallIdAdapter
from nexus.services.model_config_service import ModelConfig, fetch_model_config

logger = get_logger(__name__)


@dataclass(frozen=True)
class LLMRuntime:
    """
    单个 model_config 对应的运行时对象。
    """

    model: Any
    adapter: LiteLLMAdapter
    litellm_model: str
    model_config: ModelConfig


# 全局 LLM runtime 缓存，key 为 model_config_id。
LLM_RUNTIME_CACHE: Dict[str, LLMRuntime] = {}


def _bind_model_with_tools(
    runtime: LLMRuntime,
    tools: Optional[list],
    tool_choice: Optional[Any],
    model_config_id: int,
) -> Any:
    adapted_model = ToolCallIdAdapter(runtime.model)
    normalized_tool_choice = runtime.adapter.normalize_tool_choice_for_model(
        runtime.model_config,
        tool_choice,
    )
    if normalized_tool_choice != tool_choice:
        logger.warning(
            "步骤[模型准备]：adapter=%s 已重写 tool_choice=%s -> %s，model_config_id=%s",
            runtime.adapter.provider_id,
            str(tool_choice),
            str(normalized_tool_choice),
            model_config_id,
        )
    return adapted_model.bind_tools(tools, tool_choice=normalized_tool_choice) if tools else adapted_model


def _get_runtime(model_config_id: int, auth_token: Optional[str]) -> LLMRuntime:
    cache_key = str(model_config_id)
    cached_runtime = LLM_RUNTIME_CACHE.get(cache_key)
    if cached_runtime is not None:
        logger.info(
            "步骤[LLM]：命中缓存，adapter=%s model_id=%s model_config_id=%s",
            cached_runtime.adapter.provider_id,
            cached_runtime.litellm_model or "unknown",
            model_config_id,
        )
        return cached_runtime

    logger.info("步骤[LLM]：缓存未命中，开始创建实例，model_config_id=%s", model_config_id)
    model_config = fetch_model_config(model_config_id, auth_token)
    if not model_config:
        raise BusinessError(f"无法获取模型配置 (ID: {model_config_id})")

    try:
        adapter = LiteLLMAdapter()
        model = adapter.build_chat_model(model_config)
    except Exception as e:
        logger.error("Failed to instantiate LiteLLM adapter for config_id %s: %s", model_config_id, e)
        raise BusinessError(f"LLM 实例初始化失败: {str(e)}")

    runtime = LLMRuntime(
        model=model,
        adapter=adapter,
        litellm_model=str(model_config.litellm_model or ""),
        model_config=model_config,
    )
    LLM_RUNTIME_CACHE[cache_key] = runtime
    logger.info(
        "步骤[LLM]：实例创建成功并写入缓存，adapter=%s model_id=%s model_config_id=%s",
        runtime.adapter.provider_id,
        runtime.litellm_model or "unknown",
        model_config_id,
    )
    return runtime


def get_llm(
    model_config_id: int,
    auth_token: Optional[str],
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
) -> tuple[Any, LiteLLMAdapter]:
    """
    获取绑定工具后的 LLM 与 LiteLLM 适配器。
    """
    runtime = _get_runtime(model_config_id, auth_token)
    llm = _bind_model_with_tools(runtime, tools, tool_choice, model_config_id)
    return llm, runtime.adapter
