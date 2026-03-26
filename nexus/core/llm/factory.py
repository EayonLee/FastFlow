from __future__ import annotations

"""
LLM 运行时工厂（单内核）。

设计目标：
1) 统一一个 `get_llm` 入口
2) 把缓存、参数归一化、工具绑定和日志集中管理
3) 思考开关完全尊重数据库 `model_params_json`
"""

import json
from dataclasses import dataclass
from typing import Any, Optional

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.cache import CacheManager
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
    model_id: str
    model_config: ModelConfig
    effective_model_params: dict[str, Any]


def _serialize_model_params(model_params: dict[str, Any]) -> str:
    return json.dumps(model_params or {}, ensure_ascii=False, sort_keys=True)


def _build_cache_key(model_config_id: int) -> str:
    """
    缓存键仅按 model_config_id 区分。
    """
    return str(model_config_id)


def _bind_model_with_tools(
    runtime: LLMRuntime,
    tools: Optional[list],
    tool_choice: Optional[Any],
    model_config_id: int,
) -> Any:
    """
    把工具绑定到模型，并做 tool_choice 兼容归一化。
    """
    adapted_model = ToolCallIdAdapter(runtime.model)
    normalized_tool_choice = runtime.adapter.normalize_tool_choice(
        runtime.model_config,
        tool_choice,
    )
    if normalized_tool_choice != tool_choice:
        logger.info(
            "[模型参数兼容修正] adapter=%s tool_choice=%s->%s model_config_id=%s",
            runtime.adapter.provider_id,
            str(tool_choice),
            str(normalized_tool_choice),
            model_config_id,
        )
    if not tools:
        return adapted_model
    return adapted_model.bind_tools(tools, tool_choice=normalized_tool_choice)


def _get_runtime(model_config_id: int, auth_token: Optional[str]) -> LLMRuntime:
    """
    获取模型运行时（优先缓存）。
    """
    cache_key = _build_cache_key(model_config_id)
    cached_runtime = CacheManager.get_llm_runtime(cache_key)
    if cached_runtime is not None:
        logger.debug(
            "[模型实例获取] 命中缓存 adapter=%s model_id=%s effective_model_params=%s model_config_id=%s",
            cached_runtime.adapter.provider_id,
            cached_runtime.model_id or "unknown",
            _serialize_model_params(cached_runtime.effective_model_params),
            model_config_id,
        )
        return cached_runtime

    logger.info("[模型实例获取] 缓存未命中，开始创建实例 model_config_id=%s", model_config_id)
    model_config = fetch_model_config(model_config_id, auth_token)
    if not model_config:
        raise BusinessError(f"无法获取模型配置 (ID: {model_config_id})")

    try:
        adapter = LiteLLMAdapter()
        effective_model_params = adapter.build_model_params(model_config)
        model = adapter.build_chat_model(model_config)
    except Exception as error:
        logger.error("Failed to instantiate LiteLLM adapter for config_id %s: %s", model_config_id, error)
        raise BusinessError(f"LLM 实例初始化失败: {str(error)}")

    runtime = LLMRuntime(
        model=model,
        adapter=adapter,
        model_id=str(model_config.model_id or ""),
        model_config=model_config,
        effective_model_params=effective_model_params,
    )
    CacheManager.set_llm_runtime(cache_key, runtime)
    logger.info(
        "[模型实例获取] 创建成功并写入缓存 adapter=%s model_id=%s effective_model_params=%s model_config_id=%s",
        runtime.adapter.provider_id,
        runtime.model_id or "unknown",
        _serialize_model_params(runtime.effective_model_params),
        model_config_id,
    )
    return runtime


def get_llm(
    model_config_id: int,
    auth_token: Optional[str],
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
) -> tuple[Any, LiteLLMAdapter, str]:
    """
    获取 LLM（统一入口）。

    返回：
    - llm: 可直接调用的模型对象（按需已绑定工具）
    - adapter: LiteLLM 适配器实例
    - model_id: 当前模型 ID（用于响应标准化阶段做模型特性判断）
    """
    runtime = _get_runtime(model_config_id, auth_token)
    llm = _bind_model_with_tools(runtime, tools, tool_choice, model_config_id)
    return llm, runtime.adapter, runtime.model_id
