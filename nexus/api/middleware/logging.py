import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nexus.config.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """
        请求日志中间件，负责记录所有HTTP请求的详细信息。
        """
        # 过滤掉浏览器自动发起或爬虫请求
        ignored_paths = [
            "/.well-known/",
            "/favicon.ico",
            "/robots.txt",
            "/sitemap.xml",
        ]

        # 通过检查请求路径是否以任何被忽略的路径开头来决定是否应记录日志
        should_log = not any(
            request.url.path.startswith(path) for path in ignored_paths
        )

        start_time = time.time()  # 记录请求处理开始的时间戳

        # 请求开始
        if should_log:
            logger.info(
                f"Request BEGIN - "
                f"{request.method} {request.url.path} - "
                f"Client: {request.client.host if request.client else 'unknown'}"
            )

        # 执行请求端点
        response = await call_next(request)

        # 请求耗时
        process_time = time.time() - start_time

        # 请求结束
        if should_log:
            logger.info(
                f"Request END   - "
                f"{request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Cost: {process_time:.3f}s"  # 格式化耗时为秒，保留三位小数
            )

        response.headers["X-Process-Time"] = str(process_time)

        return response