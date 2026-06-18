import json
import logging
import logging.config
import pathlib
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.config import settings
from api.db import SessionLocal, bootstrap_sqlite_schema, engine, get_db
from api.models.profile import Profile
from api.routers import (
    ai,
    assistant,
    collection_health,
    fliclists,
    health,
    movies,
    people,
    profiles,
    search,
    ui,
)
from api.services.session import SESSION_COOKIE_NAME, get_session_secret, parse_session_token
from api.services.profiles import ROLE_ADMIN, ROLE_REVIEWER
from api.services.trusted_movies import get_untrusted_movie_ids
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
    log_style = settings.log_style.lower()
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
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    "datefmt": "%H:%M:%S",
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
LOG_STYLE = settings.log_style.lower()
LOG_COLOR = settings.log_color


def _profile_label_for_id(profile_id: Any) -> str:
    if profile_id == 1:
        return "User A"
    if profile_id == 2:
        return "User B"
    if isinstance(profile_id, int) and profile_id > 0:
        return f"Profile {profile_id}"
    return "Anonymous"


def _format_profile_label(profile_id: Any, *, colorize: bool) -> str:
    label = _profile_label_for_id(profile_id)
    if not colorize:
        return label
    if profile_id == 1:
        color = "\x1b[38;5;39m"
    elif profile_id == 2:
        color = "\x1b[38;5;214m"
    else:
        color = "\x1b[38;5;245m"
    return f"{color}{label}\x1b[0m"


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
        profile_id = getattr(request.state, "session_profile_id", None)
        profile_role = getattr(request.state, "session_profile_role", None)
        profile_label = _profile_label_for_id(profile_id)
        display_label = _format_profile_label(
            profile_id,
            colorize=LOG_STYLE in {"console", "dev"} and LOG_COLOR,
        )
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
            f"request_complete [{display_label}]",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "duration_ms": round(duration, 2),
                "profile_id": profile_id,
                "profile_role": profile_role,
                "profile_label": profile_label,
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


class AuthRequiredMiddleware(BaseHTTPMiddleware):
    """Gate non-public routes behind a signed session cookie."""

    _public_paths = {"/", "/login", "/logout", "/health", "/docs", "/redoc", "/openapi.json"}
    _public_prefixes = ("/static",)
    _api_prefixes = ("/api", "/movies", "/people", "/fliclists")
    _assistant_paths = {"/api/assistant", "/api/assistant/"}

    def _is_public(self, path: str) -> bool:
        if path in self._public_paths:
            return True
        return any(path.startswith(prefix) for prefix in self._public_prefixes)

    def _is_api(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self._api_prefixes)

    def _assistant_token_valid(self, request: Request) -> bool:
        token = settings.assistant_access_token
        if not token:
            return False
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            candidate = authorization[7:].strip()
        else:
            candidate = (
                request.headers.get("X-Vault-Assistant-Token")
                or request.headers.get("X-Assistant-Token")
                or ""
            )
        return candidate == token

    def _set_session_role(self, request: Request) -> None:
        profile_id = getattr(request.state, "session_profile_id", None)
        if not isinstance(profile_id, int) or profile_id <= 0:
            return

        db_override = request.app.dependency_overrides.get(get_db)
        db_generator = db_override() if db_override else None
        db = next(db_generator) if db_generator else SessionLocal()
        try:
            profile = db.get(Profile, profile_id)
            request.state.session_profile_role = getattr(profile, "role", None) or ROLE_REVIEWER
        finally:
            if db_generator:
                try:
                    next(db_generator)
                except StopIteration:
                    pass
            else:
                db.close()

    async def dispatch(self, request: Request, call_next):
        request.state.session_profile_id = None
        request.state.session_profile_role = None
        if request.method == "OPTIONS":
            return await call_next(request)

        if settings.disable_auth:
            request.state.session_profile_role = ROLE_ADMIN
            return await call_next(request)

        path = request.url.path
        if self._is_public(path):
            return await call_next(request)

        if path in self._assistant_paths:
            secret = get_session_secret(settings.login_session_secret)
            token = request.cookies.get(SESSION_COOKIE_NAME, "")
            session = parse_session_token(token, secret=secret)
            if session:
                request.state.session_profile_id = session.profile_id
                self._set_session_role(request)
                return await call_next(request)
            if self._assistant_token_valid(request):
                return await call_next(request)
            if not settings.assistant_access_token:
                return self._reject(request, message="Assistant token not configured.")
            return self._reject(request, message="Assistant token required.")

        secret = get_session_secret(settings.login_session_secret)
        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        session = parse_session_token(token, secret=secret)
        if not session:
            return self._reject(request, message="Login required.")

        request.state.session_profile_id = session.profile_id
        self._set_session_role(request)
        return await call_next(request)

    def _reject(self, request: Request, *, message: str):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        if self._is_api(request.url.path):
            response = _json_error(
                status.HTTP_401_UNAUTHORIZED,
                error_code="auth_required",
                message=message,
                request_id=request_id,
            )
        else:
            response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure SQLite dev databases have required tables before handling requests.
    if engine.url.get_backend_name() == "sqlite":
        bootstrap_sqlite_schema()
        if not settings.disable_auth:
            db = SessionLocal()
            try:
                get_untrusted_movie_ids(db)
            except Exception:
                logger.exception("trusted_movie_cache_warm_failed")
            finally:
                db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthRequiredMiddleware)


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
app.include_router(assistant.router)
app.include_router(ui.router)
app.include_router(fliclists.router)
app.include_router(ai.router)
app.include_router(search.router)
app.include_router(collection_health.router)
app.include_router(profiles.router)


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/login")


STATIC_DIR = pathlib.Path(__file__).resolve().parents[1] / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
