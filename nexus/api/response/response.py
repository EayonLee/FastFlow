from typing import Any, Optional
from pydantic import BaseModel
from fastapi import status


class ApiResponse(BaseModel):
    """统一返回结构。"""

    code: int = status.HTTP_200_OK
    message: str = "Success"
    data: Optional[Any] = None


def success(data: Any = None, message: str = "Success") -> ApiResponse:
    return ApiResponse(code=status.HTTP_200_OK, message=message, data=data)


def error(code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, message: str = "Error") -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)
