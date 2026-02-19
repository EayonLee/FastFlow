from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional, Tuple

from langchain_litellm import ChatLiteLLM

from nexus.services.model_config_service import ModelConfig

class LiteLLMAdapter:
    """
    基于 LiteLLM 的统一适配器：
    - 统一模型初始化（provider + model + base_url + model_params）
    - 统一工具调用约束归一化
    - 统一回答/思考内容拆分
    """

    @property
    def provider_id(self) -> str:
        return "litellm"

    @staticmethod
    def _parse_bool_setting(raw_setting: Any) -> bool:
        if isinstance(raw_setting, bool):
            return raw_setting
        if isinstance(raw_setting, (int, float)):
            return raw_setting != 0
        if isinstance(raw_setting, str):
            return raw_setting.strip().lower() in {"1", "true", "yes", "on"}
        return False

    @staticmethod
    def _parse_think_wrapped_content(content: Any) -> Tuple[str, str]:
        text = str(content or "")
        lower_text = text.lower()
        if "<think>" not in lower_text and "</think>" not in lower_text:
            return text, ""

        reasoning_parts = [
            part.strip() for part in re.findall(r"<think>([\s\S]*?)</think>", text, flags=re.IGNORECASE) if part.strip()
        ]
        if not reasoning_parts and "</think>" in lower_text and "<think>" not in lower_text:
            split_index = lower_text.find("</think>")
            maybe_reasoning = text[:split_index]
            maybe_answer = text[split_index + len("</think>") :]
            return maybe_answer.strip(), maybe_reasoning.strip()
        if not reasoning_parts and "<think>" in lower_text and "</think>" not in lower_text:
            split_index = lower_text.find("<think>")
            maybe_answer = text[:split_index]
            maybe_reasoning = text[split_index + len("<think>") :]
            return maybe_answer.strip(), maybe_reasoning.strip()

        answer_content = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
        answer_content = re.sub(r"</?think>", "", answer_content, flags=re.IGNORECASE).strip()
        reasoning_content = "\n".join(reasoning_parts)
        return answer_content, reasoning_content

    def _is_thinking_enabled(self, model_config: ModelConfig) -> bool:
        raw_setting = model_config.model_params.get("enable_thinking")
        return self._parse_bool_setting(raw_setting)

    def build_chat_model(self, model_config: ModelConfig) -> ChatLiteLLM:
        model_kwargs: Dict[str, Any] = dict(model_config.model_params or {})
        if self._is_thinking_enabled(model_config):
            model_kwargs.setdefault("enable_thinking", True)

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

    def normalize_tool_choice_for_model(self, model_config: ModelConfig, tool_choice: Optional[Any]) -> Optional[Any]:
        if not self._is_thinking_enabled(model_config):
            return tool_choice
        if tool_choice == "required" or isinstance(tool_choice, dict):
            return "auto"
        return tool_choice

    def split_response_content(
        self,
        content: Any,
        additional_kwargs: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[str, str]:
        answer_content, reasoning_content = self._parse_think_wrapped_content(content)
        payload = dict(additional_kwargs or {})

        provider_reasoning = str(payload.get("reasoning_content") or "").strip()
        if provider_reasoning:
            reasoning_content = f"{provider_reasoning}\n{reasoning_content}".strip()

        # MiniMax 等 provider 可能将思考内容放在 reasoning_details。
        reasoning_details = payload.get("reasoning_details")
        if isinstance(reasoning_details, list):
            detail_texts = []
            for item in reasoning_details:
                if isinstance(item, dict):
                    detail_text = str(item.get("text") or "").strip()
                    if detail_text:
                        detail_texts.append(detail_text)
            if detail_texts:
                merged_details = "\n".join(detail_texts)
                reasoning_content = f"{reasoning_content}\n{merged_details}".strip() if reasoning_content else merged_details

        return answer_content, reasoning_content
