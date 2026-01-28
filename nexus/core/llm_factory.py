from typing import Dict, Optional
from langchain_openai import ChatOpenAI

from nexus.common.exceptions import BusinessError
from nexus.services.model_config_service import fetch_model_config
from nexus.config.logger import get_logger

logger = get_logger(__name__)

# 全局 LLM 实例缓存，key 为 model_config_id
# 仅缓存基础模型连接，不包含 Prompt 或特定运行时参数
GLOBAL_LLM_CACHE: Dict[str, ChatOpenAI] = {}

def get_or_create_llm(
    model_config_id: int,
    auth_token: Optional[str],
    tools: Optional[list] = None,
) -> ChatOpenAI:
    """
    获取或创建一个 模型 实例。
    优化策略：优先检查全局缓存，实现不同 Agent 间的模型实例共享。
    
    :param model_config_id: 模型配置ID
    :param auth_token:      认证Token
    :param tools:           绑定的工具列表
    :return:                共享的 模型 实例
    """
    
    cache_key = str(model_config_id)

    # 1. 优先检查全局缓存
    if cache_key in GLOBAL_LLM_CACHE:
        cached_llm = GLOBAL_LLM_CACHE[cache_key]
        # 缓存存在，若需要绑定工具则返回已绑定工具的新实例，避免污染缓存
        return cached_llm.bind_tools(tools) if tools else cached_llm

    logger.info(f"LLM Cache miss for model_config_id: {model_config_id}, fetching model configuration")

    # 2. 缓存未命中，获取配置
    model_config = fetch_model_config(model_config_id, auth_token)
    if not model_config:
        raise BusinessError(f"无法获取模型配置 (ID: {model_config_id})")

    # 3. 创建基础 LLM 实例
    # 这里只设置通用的参数，特定参数（如 response_format）由具体 Agent 在运行时 bind
    llm_kwargs = {
        "model": model_config.model_id,
        "api_key": model_config.api_key,
        "streaming": True,  # 开启流式输出
    }
    
    if model_config.base_url:
        llm_kwargs["base_url"] = model_config.base_url

    try:
        llm = ChatOpenAI(**llm_kwargs)
    except Exception as e:
        logger.error(f"Failed to instantiate ChatOpenAI for config_id {model_config_id}: {e}")
        raise BusinessError(f"LLM 实例初始化失败: {str(e)}")
    
    # 4. 存入缓存
    GLOBAL_LLM_CACHE[cache_key] = llm
    logger.info(f"Created and cached LLM instance（model_id: {model_config.model_id}）for model_config_id: {model_config_id}")
    
    # 若调用方需要绑定工具，返回已绑定工具的新实例，避免污染缓存
    return llm.bind_tools(tools) if tools else llm
