"""공통 오류 형식(04_API_SPEC 0절, 03_API_PLAN 4.2절)."""
from typing import Any, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, detail: Optional[List[Any]] = None):
        self.status = status
        self.code = code
        self.message = message
        self.detail = detail


def error_body(code: str, message: str, detail: Optional[List[Any]] = None) -> dict:
    body = {"code": code, "message": message}
    if detail:
        body["detail"] = detail
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content=error_body(exc.code, exc.message, exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        detail = [
            {"field": ".".join(str(p) for p in e["loc"] if p not in ("query", "body", "path")),
             "reason": e["msg"]}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=400,
                            content=error_body("VALIDATION_ERROR", "입력 내용을 확인하십시오.", detail))

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError):
        return JSONResponse(status_code=503,
                            content=error_body("DB_UNAVAILABLE", "데이터베이스에 연결할 수 없습니다. 잠시 후 다시 시도하십시오."))
