from __future__ import annotations

"""
LiteLLM 统一适配层。

职责边界：
1) 根据模型配置创建 ChatLiteLLM 实例
2) 归一化 tool_choice 兼容策略
3) 暴露 thinking 是否启用的读取能力（仅用于日志与策略）
"""

from typing import Any, Dict, Optional

from langchain_litellm import ChatLiteLLM

from nexus.services.model_config_service import ModelConfig


class LiteLLMAdapter:
    """
    基于 LiteLLM 的轻量适配器。
    """

    @property
    def provider_id(self) -> str:
        return "litellm"

    @staticmethod
    def _parse_bool_setting(raw_setting: Any) -> bool:
        """
        将常见布尔配置值统一解析为 Python bool。
        """
        if isinstance(raw_setting, bool):
            return raw_setting
        if isinstance(raw_setting, (int, float)):
            return raw_setting != 0
        if isinstance(raw_setting, str):
            return raw_setting.strip().lower() in {"1", "true", "yes", "on"}
        return False

    def is_thinking_enabled(self, model_config: ModelConfig) -> bool:
        """
        判断当前模型配置是否开启 thinking。
        """
        raw_setting = model_config.model_params.get("enable_thinking")
        return self._parse_bool_setting(raw_setting)

    def build_model_params(self, model_config: ModelConfig) -> Dict[str, Any]:
        """
        返回传给 LiteLLM 的模型参数（原样继承数据库配置）。
        """
        model_kwargs: Dict[str, Any] = dict(model_config.model_params or {})
        if self.is_thinking_enabled(model_config):
            model_kwargs.setdefault("enable_thinking", True)
        return model_kwargs

    def build_chat_model(self, model_config: ModelConfig) -> ChatLiteLLM:
        """
        构建 ChatLiteLLM 实例。
        """
        model_kwargs = self.build_model_params(model_config)
        llm_kwargs: Dict[str, Any] = {
            "model": model_config.model_id,
            "api_key": model_config.api_key,
            "streaming": True,
            "model_kwargs": model_kwargs,
        }
        if model_config.base_url:
            llm_kwargs["api_base"] = model_config.base_url
        if model_config.provider:
            llm_kwargs["custom_llm_provider"] = model_config.provider
        return ChatLiteLLM(**llm_kwargs)

    def normalize_tool_choice(
        self,
        model_config: ModelConfig,
        tool_choice: Optional[Any],
    ) -> Optional[Any]:
        """
        归一化 tool_choice：
        - 某些开启 thinking 的模型不支持 `required` 或对象型 tool_choice；
        - 统一降级为 `auto`，避免请求直接被 provider 拒绝。
        """
        if not self.is_thinking_enabled(model_config):
            return tool_choice
        if tool_choice == "required" or isinstance(tool_choice, dict):
            return "auto"
        return tool_choice
