from fastapi import APIRouter
from nexus.config.config import get_config
from nexus.config.build_info import get_build_info
from nexus.api.response.response import ApiResponse

router = APIRouter(tags=["metrics"])

settings = get_config()
build_info = get_build_info()

@router.get(
    path="/health",
    response_model=ApiResponse,
    summary="服务健康检查",
    description="检查服务是否正常运行。"
)
def read_root():
    return {
        "data": {
            "status": "Online",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "build": build_info.to_dict(),
        }
    }
