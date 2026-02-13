from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

from nexus.common.exceptions import BusinessError
from nexus.config.logger import get_logger
from nexus.core.llm.tool_call_adapter import ToolCallIdAdapter
from nexus.services.model_config_service import fetch_model_config

logger = get_logger(__name__)

# 全局 LLM 实例缓存，key 为 model_config_id。
# 仅缓存基础模型连接，不缓存运行期参数（如 tools）。
CHAT_MODEL_CACHE: Dict[str, ChatOpenAI] = {}


def get_llm(
    model_config_id: int,
    auth_token: Optional[str],
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
) -> Any:
    """
    获取或创建共享 LLM 实例。
    """
    cache_key = str(model_config_id)
    if cache_key in CHAT_MODEL_CACHE:
        cached_model = CHAT_MODEL_CACHE[cache_key]
        adapted_model = ToolCallIdAdapter(cached_model)
        return adapted_model.bind_tools(tools, tool_choice=tool_choice) if tools else adapted_model

    logger.info("LLM cache miss for model_config_id: %s", model_config_id)
    model_config = fetch_model_config(model_config_id, auth_token)
    if not model_config:
        raise BusinessError(f"无法获取模型配置 (ID: {model_config_id})")

    llm_kwargs = {
        "model": model_config.model_id,
        "api_key": model_config.api_key,
        "streaming": True,
    }
    if model_config.base_url:
        llm_kwargs["base_url"] = model_config.base_url

    try:
        llm = ChatOpenAI(**llm_kwargs)
    except Exception as e:
        logger.error("Failed to instantiate ChatOpenAI for config_id %s: %s", model_config_id, e)
        raise BusinessError(f"LLM 实例初始化失败: {str(e)}")

    CHAT_MODEL_CACHE[cache_key] = llm
    logger.info(
        "Created and cached LLM instance (model_id: %s) for model_config_id: %s",
        model_config.model_id,
        model_config_id,
    )
    adapted_model = ToolCallIdAdapter(llm)
    return adapted_model.bind_tools(tools, tool_choice=tool_choice) if tools else adapted_model
