"""
Skill 工具（本地 skill runtime）。

用途：
- 列出可用 skills 摘要
- 按需加载 skill 正文
- 按需读取 skill 资源文件
"""

from __future__ import annotations

import json
from typing import List, Tuple

from langchain_core.tools import tool

from nexus.config.logger import get_logger, log_tool_failure, log_tool_success
from nexus.core.schemas import ChatRequestContext
from nexus.core.skills import SkillRuntime

logger = get_logger(__name__)


class SkillTools:
    """
    本地 Skill 工具实现。
    """

    def __init__(self, context: ChatRequestContext):
        self.context = context
        self._runtime = SkillRuntime()

    def list_skills(self) -> str:
        skill_summaries = self._runtime.list_skills()
        result_json = json.dumps({"skills": skill_summaries}, ensure_ascii=False)
        log_tool_success(logger, "list_skills", count=len(skill_summaries))
        return result_json

    def load_skill(self, skill_name: str) -> str:
        try:
            skill_payload = self._runtime.load_skill(skill_name)
        except Exception as error:
            error_result_json = json.dumps(
                {"error": str(error), "skill_name": str(skill_name or "")},
                ensure_ascii=False,
            )
            log_tool_failure(logger, "load_skill", error=str(error), skill_name=str(skill_name or ""))
            return error_result_json

        result_json = json.dumps(skill_payload, ensure_ascii=False)
        log_tool_success(
            logger,
            "load_skill",
            skill_name=skill_name,
            resource_count=len(skill_payload.get("resource_paths", [])),
            content_length=len(str(skill_payload.get("content") or "")),
        )
        return result_json

    def load_skill_resource(self, skill_name: str, resource_path: str) -> str:
        try:
            resource_payload = self._runtime.load_skill_resource(skill_name, resource_path)
        except Exception as error:
            error_result_json = json.dumps(
                {
                    "error": str(error),
                    "skill_name": str(skill_name or ""),
                    "resource_path": str(resource_path or ""),
                },
                ensure_ascii=False,
            )
            log_tool_failure(
                logger,
                "load_skill_resource",
                error=str(error),
                skill_name=str(skill_name or ""),
                resource_path=str(resource_path or ""),
            )
            return error_result_json

        result_json = json.dumps(resource_payload, ensure_ascii=False)
        log_tool_success(
            logger,
            "load_skill_resource",
            skill_name=skill_name,
            resource_path=resource_path,
            content_length=len(str(resource_payload.get("content") or "")),
        )
        return result_json


def build_skill_tools(context: ChatRequestContext) -> Tuple[List, SkillTools]:
    """
    构建 Skill 工具列表。
    """
    tool_impl = SkillTools(context)

    @tool
    def list_skills():
        """
        列出当前 skills 摘要（返回 `skill_name/name/description/enabled`）。
        当需要专业流程（如提示词优化、提示词生成）时，先调用此工具再决定是否加载具体 skill。
        """
        return tool_impl.list_skills()

    @tool
    def load_skill(skill_name: str):
        """
        加载指定 skill 的正文内容（`SKILL.md`），并返回可读取的资源路径列表。
        `skill_name` 必须是 `skills/<skill_name>/SKILL.md` 中的目录名。
        对提示词任务，优先加载 `prompt-optimize` 获取“只输出提示词正文”的执行规则。
        """
        return tool_impl.load_skill(skill_name)

    @tool
    def load_skill_resource(skill_name: str, resource_path: str):
        """
        加载 skill 的资源文件内容（例如 `references/*.md`、`scripts/*.py`）。
        `resource_path` 必须是 skill 目录内相对路径。
        仅在 skill 正文不足以完成任务时再调用，避免无意义读取。
        """
        return tool_impl.load_skill_resource(skill_name, resource_path)

    return [list_skills, load_skill, load_skill_resource], tool_impl


__all__ = ["SkillTools", "build_skill_tools"]
