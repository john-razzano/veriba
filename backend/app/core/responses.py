from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError


def success_response(data, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": True, "data": jsonable_encoder(data), "error": None},
    )


def error_response(
    message: str,
    *,
    status_code: int,
    code: str,
    details=None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": code, "message": message, "details": jsonable_encoder(details)},
        },
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return error_response(detail, status_code=exc.status_code, code="http_error")


async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        "Validation failed",
        status_code=422,
        code="validation_error",
        details=exc.errors(),
    )


async def integrity_exception_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    return error_response(
        "Database constraint violated",
        status_code=409,
        code="integrity_error",
        details=str(exc.orig),
    )


async def rate_limit_exception_handler(_: Request, __: RateLimitExceeded) -> JSONResponse:
    return error_response(
        "Rate limit exceeded",
        status_code=429,
        code="rate_limited",
    )


def register_exception_handlers(app) -> None:
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)

