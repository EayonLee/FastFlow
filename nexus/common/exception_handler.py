from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common.exceptions import BusinessError, AuthError, ParmasValidationError
from config.logger import get_logger

logger = get_logger(__name__)

def register_exception_handlers(app: FastAPI):
    """
    注册全局异常处理器
    """
    
    @app.exception_handler(ParmasValidationError)
    async def validation_exception_handler(request: Request, exc: ParmasValidationError):
        return JSONResponse(
            status_code=200,
            content={
                "code": 422,
                "message": exc.message,
                "data": None
            }
        )

    @app.exception_handler(AuthError)
    async def auth_exception_handler(request: Request, exc: AuthError):
        return JSONResponse(
            status_code=200,
            content={
                "code": 401,
                "message": exc.message,
                "data": None
            }
        )

    @app.exception_handler(BusinessError)
    async def business_exception_handler(request: Request, exc: BusinessError):
        return JSONResponse(
            status_code=200,
            content={
                "code": 500,
                "message": exc.message,
                "data": None
            }
        )
