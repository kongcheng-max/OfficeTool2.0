"""全局异常处理"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from core.response import APIResponse


class AppException(Exception):
    """业务异常基类"""

    def __init__(self, code: int = 1, message: str = "内部错误"):
        self.code = code
        self.message = message


class NotFoundError(AppException):
    """资源不存在"""

    def __init__(self, resource: str = "资源"):
        super().__init__(code=404, message=f"{resource}不存在")


class UnauthorizedError(AppException):
    """未认证"""

    def __init__(self, message: str = "请先登录"):
        super().__init__(code=401, message=message)


class ForbiddenError(AppException):
    """无权限"""

    def __init__(self, message: str = "无操作权限"):
        super().__init__(code=403, message=message)


class BadRequestError(AppException):
    """请求参数错误"""

    def __init__(self, message: str = "请求参数有误"):
        super().__init__(code=400, message=message)


class ConflictError(AppException):
    """资源冲突（如重复）"""

    def __init__(self, message: str = "资源已存在"):
        super().__init__(code=409, message=message)


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(f"业务异常: [{exc.code}] {exc.message}")
        return JSONResponse(
            status_code=exc.code if exc.code >= 400 else 200,
            content=APIResponse.error(exc.code, exc.message).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        detail = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in errors
        )
        logger.warning(f"参数校验失败: {detail}")
        return JSONResponse(
            status_code=422,
            content=APIResponse.error(422, f"参数校验失败: {detail}").model_dump(),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"未捕获异常: {exc}")
        return JSONResponse(
            status_code=500,
            content=APIResponse.error(500, "服务器内部错误").model_dump(),
        )
