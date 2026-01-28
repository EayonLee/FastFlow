from fastapi import APIRouter
from config.config import get_config
from api.response.response import ApiResponse

router = APIRouter(tags=["metrics"])

settings = get_config()

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
            "version": settings.APP_VERSION
        }
    }
