"""
Skill 运行时（本地文件系统版）。

目录约定：
- `nexus/skills/<skill_name>/SKILL.md`
- 可选资源目录：`references/`、`scripts/`、`assets/`

渐进式披露：
1) `list_skills` 返回 `skill_name/name/description/enabled`
2) `load_skill` 返回 SKILL.md 正文 + 可读取资源路径
3) `load_skill_resource` 读取具体资源文件
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

SKILL_FILE_NAME = "SKILL.md"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n)?", re.DOTALL)
TRUTHY_VALUES = {"1", "true", "yes", "on"}
RESOURCE_DIR_NAMES = ("references", "scripts", "assets")
SKILL_ROOT_DIR = Path(__file__).resolve().parents[2] / "skills"


def _parse_frontmatter(skill_markdown: str) -> Tuple[Dict[str, str], str]:
    """
    解析 SKILL.md frontmatter。

    仅支持最常见的 `key: value` 行格式；无法解析时按“无 frontmatter”处理。
    """
    match = FRONTMATTER_PATTERN.match(skill_markdown)
    if not match:
        return {}, skill_markdown

    frontmatter_text = match.group(1).strip()
    metadata: Dict[str, str] = {}
    for raw_line in frontmatter_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'").strip('"')
    return metadata, skill_markdown[match.end() :]


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return default
    return normalized in TRUTHY_VALUES


class SkillRuntime:
    """
    本地 Skill 读取器。
    """

    def __init__(self, root_dir: Path | None = None):
        self.root_dir = (root_dir or SKILL_ROOT_DIR).resolve()

    def _validate_skill_name(self, skill_name: str) -> str:
        normalized = str(skill_name or "").strip()
        if not SKILL_NAME_PATTERN.fullmatch(normalized):
            raise ValueError(f"invalid skill_name: {normalized}")
        return normalized

    def _get_skill_dir(self, skill_name: str) -> Path:
        normalized = self._validate_skill_name(skill_name)
        skill_dir = (self.root_dir / normalized).resolve()
        try:
            skill_dir.relative_to(self.root_dir)
        except ValueError as error:
            raise ValueError(f"skill path out of root: {normalized}") from error
        return skill_dir

    def _load_skill_doc(self, skill_name: str) -> Dict[str, Any]:
        skill_dir = self._get_skill_dir(skill_name)
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"skill not found: {skill_name}")

        skill_file = skill_dir / SKILL_FILE_NAME
        if not skill_file.is_file():
            raise FileNotFoundError(f"missing {SKILL_FILE_NAME}: {skill_name}")

        raw_text = skill_file.read_text(encoding="utf-8")
        metadata, content = _parse_frontmatter(raw_text)
        return {
            "skill_name": skill_name,
            "name": str(metadata.get("name") or skill_name),
            "description": str(metadata.get("description") or "").strip(),
            "enabled": _parse_bool(metadata.get("enabled"), default=True),
            "content": content.strip(),
            "skill_dir": skill_dir,
        }

    def _build_resource_paths(self, skill_dir: Path) -> List[str]:
        resource_paths: List[str] = []
        for dirname in RESOURCE_DIR_NAMES:
            resource_dir = skill_dir / dirname
            if not resource_dir.is_dir():
                continue
            for file_path in sorted(resource_dir.rglob("*")):
                if file_path.is_file():
                    resource_paths.append(str(file_path.relative_to(skill_dir)))
        return resource_paths

    def list_skills(self) -> List[Dict[str, Any]]:
        """
        返回 skill 摘要（第一层披露）。
        """
        if not self.root_dir.is_dir():
            return []

        skills: List[Dict[str, Any]] = []
        for candidate in sorted(self.root_dir.iterdir(), key=lambda item: item.name):
            if not candidate.is_dir() or not SKILL_NAME_PATTERN.fullmatch(candidate.name):
                continue
            try:
                skill_doc = self._load_skill_doc(candidate.name)
            except (FileNotFoundError, PermissionError, OSError, ValueError):
                continue
            skills.append(
                {
                    "skill_name": skill_doc["skill_name"],
                    "name": skill_doc["name"],
                    "description": skill_doc["description"],
                    "enabled": bool(skill_doc["enabled"]),
                }
            )
        return skills

    def load_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        返回 skill 正文与资源清单（第二层披露）。
        """
        skill_doc = self._load_skill_doc(skill_name)
        if not bool(skill_doc["enabled"]):
            raise PermissionError(f"skill disabled: {skill_name}")

        skill_dir = skill_doc["skill_dir"]
        return {
            "skill_name": skill_doc["skill_name"],
            "name": skill_doc["name"],
            "description": skill_doc["description"],
            "content": skill_doc["content"],
            "resource_paths": self._build_resource_paths(skill_dir),
        }

    def load_skill_resource(self, skill_name: str, resource_path: str) -> Dict[str, Any]:
        """
        读取 skill 资源文件（第三层披露）。
        """
        skill_doc = self._load_skill_doc(skill_name)
        if not bool(skill_doc["enabled"]):
            raise PermissionError(f"skill disabled: {skill_name}")

        normalized_path = str(resource_path or "").strip()
        if not normalized_path:
            raise ValueError("resource_path is empty")

        skill_dir = skill_doc["skill_dir"]
        file_path = (skill_dir / normalized_path).resolve()
        try:
            file_path.relative_to(skill_dir)
        except ValueError as error:
            raise ValueError(f"resource path out of skill directory: {normalized_path}") from error
        if not file_path.is_file():
            raise FileNotFoundError(f"resource not found: {normalized_path}")

        return {
            "skill_name": skill_doc["skill_name"],
            "resource_path": normalized_path,
            "content": file_path.read_text(encoding="utf-8"),
        }
