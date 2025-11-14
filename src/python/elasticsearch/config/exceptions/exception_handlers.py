from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.python.elasticsearch.config.exceptions.biz_exceptions import BizException
from src.python.elasticsearch.application.schemas.responses.common.common_res import CommonRes


def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    HTTP 예외 헨들러 (404, 403 등)
    :param request:
    :param exc:
    :return:
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=CommonRes(code=str(exc.status_code), message=str(exc.detail)).model_dump()
    )

def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    FastAPI 데이터 검증 실패 예외 헨들어 (Pydantic Validation Error)
    :param request:
    :param exc:
    :return:
    """
    return JSONResponse(
        status_code=400,
        content=CommonRes(code="400", message="Validation error", data=exc.errors()).model_dump()
    )

def internal_server_error_handler(request: Request, exc: Exception):
    """
    500 Internal Server Error 예외 핸들러
    :param request:
    :param exc:
    :return:
    """
    return JSONResponse(
        status_code=500,
        content=CommonRes(code="500", message=str(exc)).model_dump()
    )

def biz_exception_handler(request: Request, exc: BizException):
    """
    Biz 예외 헨들러
    :param request:
    :param exc:
    :return:
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=CommonRes(code=str(exc.status_code), message=str(exc.detail)).model_dump()
    )