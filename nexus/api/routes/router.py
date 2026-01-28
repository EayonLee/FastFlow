from fastapi import APIRouter

from api.metrics import router as metrics_router
from api.agent import router as agent_router

# 统一的基础路由，便于聚合版本前缀并集中注册子路由
base_router = APIRouter(prefix="/fastflow/nexus/v1")

# 注册业务与监控路由（子路由自身已包含版本前缀）
base_router.include_router(metrics_router)
base_router.include_router(agent_router)
