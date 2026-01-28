from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from nexus.api.routes.router import base_router
from nexus.config.config import get_config
from nexus.config.logger import setup_logging, get_logger
from nexus.common.exception_handler import register_exception_handlers

# 获取配置实例
settings = get_config()

# 设置日志配置
setup_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    try:
        logger.info(f"🚀 {settings.APP_NAME} is starting up...")
    except Exception as e:
        logger.error(f"❌ App startup failed: {e}")
        raise

    yield

    logger.info(f"👋 {settings.APP_NAME} is shutting down...")


def create_app() -> FastAPI:
    """
    创建和配置FastAPI应用实例
    """
    # 创建FastAPI应用
    application = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan
    )

    # 配置可信主机中间件
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.APP_HOST, "localhost", "127.0.0.1"]  # 允许的主机列表
    )

    # 配置 CORS 中间件，允许 Chrome 插件访问
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有来源，生产环境应限制为特定 extension id
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载业务路由
    application.include_router(base_router)

    # 注册全局异常处理器
    register_exception_handlers(application)

    return application


# 创建应用实例
app = create_app()


def main() -> None:
    """
    应用程序主入口点, 配置并启动Uvicorn服务器
    """

    # 启动信息
    display_host = "localhost" if settings.APP_HOST == "0.0.0.0" else settings.APP_HOST
    logger.info(
        f"\n"
        f"      🌟 Server Name    : {settings.APP_NAME}\n"
        f"      📍 Server Address : http://{display_host}:{settings.APP_PORT}\n"
    )

    # 启动服务器
    uvicorn.run(
        "nexus.main:app",  # 应用实例
        host=settings.APP_HOST,  # 主机地址
        port=settings.APP_PORT,  # 端口号
        reload=settings.LOG_LEVEL.upper() == "DEBUG",  # 自动重载，仅在DEBUG模式下启用
        log_level=settings.LOG_LEVEL.lower(),  # 日志级别
        access_log=False,  # 是否开启访问日志，False: 不开启, 为了不跟日志中间件的效果冲突，此处关闭
        server_header=False,  # 是否显示服务器信息，False: 不显示
        date_header=False,  # 是否显示日期头，False: 不显示
        log_config=None  # 禁用uvicorn默认日志配置，使用统一格式
    )


if __name__ == "__main__":
    main()
