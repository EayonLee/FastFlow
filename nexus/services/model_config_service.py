import httpx
import json
from json import JSONDecodeError
from typing import Any, Dict, Optional
from nexus.config.config import get_config
from nexus.config.logger import get_logger
from nexus.common.exceptions import BusinessError
from pydantic import BaseModel, Field

# 获取全局配置
settings = get_config()
logger = get_logger(__name__)
SUCCESS_CODES = {0, 200}
MODEL_CONFIG_PATH = "/fastflow/api/v1/model_config/{}"


class ModelConfig(BaseModel):
    model_name: Optional[str] = None
    litellm_model: str
    provider: Optional[str] = None
    api_key: str
    base_url: Optional[str] = None
    model_params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


def _parse_model_params(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except JSONDecodeError:
            logger.warning("Invalid model_params_json, fallback to empty object.")
            return {}
    return {}


def _parse_enabled(raw_value: Any) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, (int, float)):
        return raw_value != 0
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        return normalized in {"1", "true", "yes", "on"}
    return True


def _build_headers(auth_token: Optional[str]) -> dict[str, str]:
    if not auth_token:
        return {}
    return {"Authorization": auth_token}


def _is_success(code: object) -> bool:
    return code in SUCCESS_CODES


def fetch_model_config(model_config_id: int, auth_token: Optional[str] = None) -> Optional[ModelConfig]:
    """
    获取完整的模型配置
    
    Args:
        model_config_id: 模型配置 ID
        auth_token:      用户认证 Token (用于鉴权)
        
    Returns:
        ModelConfig 对象，如果获取失败则返回 None
    """
    # 获取模型配置信息
    url = f"{settings.FASTFLOW_API_URL}{MODEL_CONFIG_PATH.format(model_config_id)}"
    try:
        # 使用同步请求，显式禁用代理（避免 VPN/系统代理干扰本地请求）
        with httpx.Client(trust_env=False) as client:
            response = client.get(
                url,
                headers=_build_headers(auth_token),
                timeout=5.0,
            )
        response.raise_for_status()
        data = response.json()

        if not _is_success(data.get("code")):
            error_msg = data.get("message", "Unknown Error")
            logger.error("Failed to fetch Model Config for id %s, error: %s", model_config_id, error_msg)
            raise BusinessError(f"获取模型配置失败: {error_msg}")

        result = data.get("data", {})
        api_key = _decrypt_key(result.get("apiKey"))
        if not api_key:
            return None

        litellm_model = str(result.get("litellmModel") or "").strip()
        if not litellm_model:
            raise BusinessError("模型配置缺少 litellmModel")

        enabled = _parse_enabled(result.get("enabled", True))
        if not enabled:
            raise BusinessError("当前模型配置已禁用，请切换其他模型")

        logger.debug("Successfully fetched Model Config for model_config_id: %s", model_config_id)
        return ModelConfig(
            model_name=result.get("modelName"),
            litellm_model=litellm_model,
            provider=result.get("provider"),
            api_key=api_key,
            base_url=result.get("baseUrl"),
            model_params=_parse_model_params(result.get("modelParamsJson")),
            enabled=enabled,
        )
    except BusinessError:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(
            "Error fetching Model Config for id %s, status=%s body=%s",
            model_config_id,
            e.response.status_code,
            e.response.text,
        )
        raise BusinessError(f"获取模型配置时发生错误: {str(e)}")
    except Exception as e:
        logger.error("Error fetching Model Config for id %s: %s", model_config_id, e)
        raise BusinessError(f"获取模型配置时发生错误: {str(e)}")

def _decrypt_key(encrypted_key: str) -> str:
    """
    解密 Nexus Key。
    目前假设后端返回的是明文（或者 Nexus 暂时没有解密逻辑）。
    如果后端真正加密了，这里需要实现解密算法（如 AES）。
    """
    if not encrypted_key:
        return ""
    
    # TODO: 实现真正的解密逻辑
    # 比如: return decrypt_aes(encrypted_key, SECRET)
    
    return encrypted_key
