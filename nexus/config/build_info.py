from __future__ import annotations

from dataclasses import dataclass

from nexus.config.config import get_config


@dataclass(frozen=True)
class BuildInfo:
    """
    服务构建指纹。

    用于确认当前进程实际运行的是哪一版构建产物，避免“源码已变更、
    容器仍跑旧代码”时难以定位。
    """

    version: str
    git_sha: str
    build_time: str

    def to_dict(self) -> dict[str, str]:
        return {
            "version": self.version,
            "git_sha": self.git_sha,
            "build_time": self.build_time,
        }


def get_build_info() -> BuildInfo:
    settings = get_config()
    return BuildInfo(
        version=str(settings.APP_VERSION or "").strip() or "unknown",
        git_sha=str(settings.BUILD_GIT_SHA or "").strip() or "unknown",
        build_time=str(settings.BUILD_TIME or "").strip() or "unknown",
    )
