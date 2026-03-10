"""
Slash 目录接口。

用途：
1) 提供 `/` 上拉面板所需的 skills 列表；
2) 返回 MCP 占位分组，便于前端提前渲染分组结构；
3) 除 agent/builder 流式接口外，统一使用 ApiResponse 返回结构。
"""

from fastapi import APIRouter, Request

from nexus.common.exceptions import AuthError
from nexus.api.response.response import ApiResponse
from nexus.services.auth_service import check_login
from nexus.core.skills.runtime import SkillRuntime

# 路由分组：对外路径前缀为 /fastflow/nexus/v1/slash
router = APIRouter(prefix="/slash", tags=["slash"])


@router.get("/catalog", response_model=ApiResponse)
async def get_slash_catalog(request: Request):
    """
    返回 slash 面板目录：
    - skills: 本地可用 skill 列表
    - mcp: 占位分组（后续扩展）
    """
    # 1) 从请求头读取登录态。
    auth_token = request.headers.get("Authorization")
    if not auth_token:
        raise AuthError("Authorization token is required")
    # 2) 复用现有认证服务校验登录状态。
    if not check_login(auth_token):
        raise AuthError("Current user is not logged in")

    # 3) 读取本地 skills 目录，返回可见条目。
    skill_runtime = SkillRuntime()
    skills = skill_runtime.list_skills()

    # 4) MCP 先返回占位分组：前端可以先完成交互布局，后续再接真实 MCP 目录。
    mcp_placeholder = [
        {
            "key": "mcp",
            "name": "MCP",
            "description": "MCP 选择即将开放",
            "disabled": True,
        }
    ]

    # 5) 按统一结构返回：{code, message, data}。
    return {
        "data": {
            "skills": skills,
            "mcp": mcp_placeholder,
        }
    }
