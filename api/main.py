import json
import logging
import logging.config
import os
import pathlib
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import settings
from api.db import bootstrap_sqlite_schema, engine
from api.routers import (
    ai,
    collection_health,
    fliclists,
    health,
    movies,
    people,
    profiles,
    search,
    ui,
)
import api.models  # noqa: F401  # ensure all model mappers are registered


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload)


def configure_logging() -> None:
    log_style = os.getenv("LOG_STYLE", "json").lower()
    formatter = "console" if log_style in {"console", "dev"} else "json"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": JsonFormatter,
                },
                "console": {
                    # Dev-friendly format; keep JSON for log processors.
                    "format": "%(levelname)s %(name)s %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter,
                }
            },
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": "INFO"},
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
                "vault966": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
            "root": {"handlers": ["console"], "level": "INFO"},
        }
    )


configure_logging()

logger = logging.getLogger("vault966")


def _safe_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict) and "msg" in first:
            return str(first.get("msg"))
        return str(first)
    return str(detail) if detail is not None else "Unexpected error"


def _json_error(
    status_code: int, *, error_code: str, message: str, request_id: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "request_id": request_id,
        },
    )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()
        response = None
        status_code = 500
        error_handled = False
        try:
            response = await call_next(request)
            status_code = response.status_code
        except RequestValidationError as exc:
            status_code = 422
            message = _safe_message(exc.errors())
            response = _json_error(
                status_code,
                error_code="validation_error",
                message=message,
                request_id=request_id,
            )
            error_handled = True
        except HTTPException as exc:
            status_code = exc.status_code
            message = _safe_message(exc.detail)
            error_code = "validation_error" if status_code == 422 else "http_error"
            response = _json_error(
                status_code,
                error_code=error_code,
                message=message,
                request_id=request_id,
            )
            error_handled = True
        except Exception:  # pragma: no cover - defensive
            status_code = 500
            logger.exception(
                "unhandled_exception",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            response = _json_error(
                status_code,
                error_code="internal_error",
                message="Internal server error",
                request_id=request_id,
            )
            error_handled = True

        duration = (time.perf_counter() - start) * 1000
        if (
            not error_handled
            and response is not None
            and response.status_code >= 400
            and getattr(response, "body", None) is not None
        ):
            message = None
            try:
                body = json.loads(response.body.decode()) if response.body else {}
                if isinstance(body, dict) and "detail" in body:
                    message = _safe_message(body["detail"])
            except Exception:
                message = None
            if message:
                response = _json_error(
                    response.status_code,
                    error_code="http_error",
                    message=message,
                    request_id=request_id,
                )

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_complete",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": round(duration, 2),
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "img-src 'self' data: https:; "
            "script-src 'self'; "
            "script-src-attr 'none'; "
            "style-src 'self'; "
            "style-src-attr 'none'; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure SQLite dev databases have required tables before handling requests.
    if engine.url.get_backend_name() == "sqlite":
        bootstrap_sqlite_schema()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    message = _safe_message(exc.detail)
    error_code = "validation_error" if exc.status_code == 422 else "http_error"
    response = _json_error(
        exc.status_code,
        error_code=error_code,
        message=message,
        request_id=request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    message = _safe_message(exc.errors())
    response = _json_error(
        422,
        error_code="validation_error",
        message=message,
        request_id=request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    message = _safe_message(exc.detail)
    response = _json_error(
        exc.status_code,
        error_code="http_error",
        message=message,
        request_id=request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


# CORS (for future Next.js frontend)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Content-Length", "Content-Type"],
        max_age=600,
    )

app.include_router(health.router)
app.include_router(movies.router)
app.include_router(people.router)
app.include_router(ui.router)
app.include_router(fliclists.router)
app.include_router(ai.router)
app.include_router(search.router)
app.include_router(collection_health.router)
app.include_router(profiles.router)


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/ui/movies")


STATIC_DIR = pathlib.Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
