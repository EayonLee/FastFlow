
class BusinessError(Exception):
    """
    通用业务异常基类。
    用于替代 ValueError 等标准异常，以便在 API 层统一捕获处理，
    并提供更清晰的错误信息给前端，避免暴露复杂的堆栈信息。
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

    def __str__(self):
        return f"{self.message}"


class AuthError(BusinessError):
    """
    认证相关异常，继承自 BusinessError。
    用于处理登录失败、Token 无效等情况。
    """
    def __init__(self, message: str):
        super().__init__(message)

class ParmasValidationError(BusinessError):
    """
    请求参数校验异常，继承自 BusinessError。
    用于处理请求参数不符合预期的情况。
    """
    def __init__(self, message: str):
        super().__init__(message)