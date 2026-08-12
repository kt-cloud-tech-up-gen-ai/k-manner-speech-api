"""Public HTTP error envelope and secret-safe request logging."""

import json
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_cors_allow_origins
from app.core.db import DatabaseConfigurationError

logger = logging.getLogger("app.http")


def _code_for(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }.get(status_code, "HTTP_ERROR")


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "status": status_code}},
    )


def _message(detail: Any, fallback: str) -> str:
    return detail if isinstance(detail, str) else fallback


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DatabaseConfigurationError)
    async def handle_database_configuration(
        _request: Request, _exc: DatabaseConfigurationError
    ) -> JSONResponse:
        return error_response(
            503,
            "SERVICE_UNAVAILABLE",
            "데이터베이스가 구성되지 않았습니다.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        response = error_response(
            exc.status_code,
            _code_for(exc.status_code),
            _message(exc.detail, "요청을 처리할 수 없습니다."),
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "VALIDATION_ERROR", "입력값을 확인해 주세요.")

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, _exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        logger.error(
            json.dumps(
                {"request_id": request_id, "path": request.url.path, "status": 500},
                ensure_ascii=False,
            )
        )
        response = error_response(
            500,
            "INTERNAL_SERVER_ERROR",
            "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )
        response.headers["X-Request-ID"] = request_id
        origin = request.headers.get("Origin")
        if origin in get_cors_allow_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
