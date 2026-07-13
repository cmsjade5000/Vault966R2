from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.services.profiles import (
    PROFILE_COOKIE_NAME,
    ensure_profile_cookie,
    get_profiles,
    set_active_profile_cookie,
)
from api.services.session import (
    SESSION_COOKIE_NAME,
    create_session_token,
    get_session_secret,
    parse_session_token,
)
from api.services.setup import (
    db_credentials_configured,
    is_setup_complete,
    matching_db_credential_profile_id,
)
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH
from api.services.ui.templates import TEMPLATES

router = APIRouter()

PROFILE_PICKER_LABELS = ("User A", "User B")
UNLOCK_COOKIE_NAME = "vault_unlock"
UNLOCK_TOKEN_VERSION = 1
UNLOCK_TTL_SECONDS = 5 * 60
PUBLIC_ARCHIVE_IMAGE_PATHS = (
    "img/app-icon.png",
    "img/apple-touch-icon.png",
    "img/android-chrome-512x512.png",
    "img/splash-1024.png",
    "img/splash-1536x2048.png",
    "img/splash-1668x2224.png",
    "img/splash-1668x2388.png",
    "img/splash-2048x1536.png",
    "img/splash-2048x2732.png",
    "img/splash-2224x1668.png",
    "img/splash-2388x1668.png",
    "img/splash-2732x2048.png",
)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(payload: str) -> str:
    secret = get_session_secret(settings.login_session_secret)
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _create_unlock_token(profile_id: int | None) -> str:
    now = int(time.time())
    payload = {
        "v": UNLOCK_TOKEN_VERSION,
        "profile_id": profile_id,
        "iat": now,
        "exp": now + UNLOCK_TTL_SECONDS,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64encode(payload_raw)
    return f"{payload_b64}.{_sign(payload_b64)}"


def _parse_unlock_token(token: str) -> int | None:
    if not token or "." not in token:
        return None
    payload_b64, signature = token.split(".", 1)
    if not hmac.compare_digest(signature, _sign(payload_b64)):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("v") != UNLOCK_TOKEN_VERSION:
        return None
    try:
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError):
        return None
    if expires_at <= int(time.time()):
        return None
    raw_profile_id = payload.get("profile_id")
    if raw_profile_id is None:
        return 0
    try:
        profile_id = int(raw_profile_id)
    except (TypeError, ValueError):
        return None
    return profile_id if profile_id > 0 else None


def _session_profile_id(request: Request) -> Optional[int]:
    secret = get_session_secret(settings.login_session_secret)
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    session = parse_session_token(token, secret=secret)
    if session:
        return session.profile_id
    return None


def _public_archive_image_urls(request: Request) -> list[str]:
    return [
        str(request.url_for("static", path=image_path)) for image_path in PUBLIC_ARCHIVE_IMAGE_PATHS
    ]


def _archive_tiles(urls: list[str], *, limit: int = 12) -> list[Optional[str]]:
    tiles: list[Optional[str]] = list(urls[:limit])
    if len(tiles) < limit:
        tiles.extend([None] * (limit - len(tiles)))
    return tiles


def _wants_json(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept


def _profile_picker_options(profiles) -> list[dict[str, int | str]]:
    options = []
    for index, profile in enumerate(profiles):
        if profile.id is None:
            continue
        label = profile.name or (
            PROFILE_PICKER_LABELS[index]
            if index < len(PROFILE_PICKER_LABELS)
            else f"Profile {profile.id}"
        )
        options.append({"id": profile.id, "label": label})
    return options


def _credential_pairs(profiles) -> list[tuple[int | None, str, str]]:
    pairs: list[tuple[int | None, str, str]] = []
    profile_options = _profile_picker_options(profiles)
    if (
        settings.login_access_key_user_a
        and settings.login_passcode_user_a
        and len(profile_options) >= 1
    ):
        pairs.append(
            (
                int(profile_options[0]["id"]),
                settings.login_access_key_user_a,
                settings.login_passcode_user_a,
            )
        )
    if (
        settings.login_access_key_user_b
        and settings.login_passcode_user_b
        and len(profile_options) >= 2
    ):
        pairs.append(
            (
                int(profile_options[1]["id"]),
                settings.login_access_key_user_b,
                settings.login_passcode_user_b,
            )
        )
    if settings.login_access_key and settings.login_passcode:
        pairs.append((None, settings.login_access_key, settings.login_passcode))
    return pairs


def _login_credentials_configured(profiles) -> bool:
    return bool(_credential_pairs(profiles))


def _credentials_available(db: Session, profiles) -> bool:
    return _login_credentials_configured(profiles) or db_credentials_configured(db)


def _credentials_match(
    db: Session,
    profiles,
    *,
    access_key: str | None,
    passcode: str | None,
) -> int | None:
    candidate_key = (access_key or "").strip()
    candidate_passcode = (passcode or "").strip()
    if not candidate_key or not candidate_passcode:
        return None
    db_profile_id = matching_db_credential_profile_id(
        db,
        access_key=candidate_key,
        passcode=candidate_passcode,
    )
    if db_profile_id is not None:
        return db_profile_id
    for profile_id, expected_key, expected_passcode in _credential_pairs(profiles):
        if hmac.compare_digest(candidate_key, expected_key) and hmac.compare_digest(
            candidate_passcode, expected_passcode
        ):
            return profile_id or 0
    return None


def _login_template_context(
    request: Request,
    profiles,
    *,
    active_profile_id: int | None = None,
    default_profile_id: int | None = None,
    error: str | None = None,
    unlocked: bool = False,
    credentials_unavailable: bool = False,
) -> dict:
    archive_poster_urls = _public_archive_image_urls(request)
    return {
        "profiles": profiles,
        "active_profile_id": active_profile_id,
        "error": error,
        "unlocked": unlocked,
        "credentials_unavailable": credentials_unavailable,
        "default_profile_id": default_profile_id,
        "profile_options": _profile_picker_options(profiles),
        "archive_tiles": _archive_tiles(archive_poster_urls),
        "archive_poster_urls": archive_poster_urls,
    }


def _render_login_error(
    request: Request,
    profiles,
    *,
    message: str,
    status_code: int,
    credentials_unavailable: bool = False,
):
    return TEMPLATES.TemplateResponse(
        request,
        "login.html",
        _login_template_context(
            request,
            profiles,
            error=message,
            credentials_unavailable=credentials_unavailable,
        ),
        status_code=status_code,
    )


@router.get("/login", response_class=HTMLResponse)
def login(
    request: Request,
    unlocked: Optional[int] = Query(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
):
    """Public login landing page (no auth required)."""
    if not settings.disable_auth and not is_setup_complete(db):
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)
    profiles = get_profiles(db)
    default_profile_id = profiles[0].id if profiles else None

    unlocked_state = bool(unlocked)
    if _session_profile_id(request) and not unlocked_state:
        return RedirectResponse(url="/ui/movies", status_code=status.HTTP_302_FOUND)

    if not settings.disable_auth and not _credentials_available(db, profiles):
        return _render_login_error(
            request,
            profiles,
            message="Login credentials are not configured.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            credentials_unavailable=True,
        )

    active_profile_id = None
    if request.cookies.get(PROFILE_COOKIE_NAME):
        try:
            active_profile_id = int(request.cookies.get(PROFILE_COOKIE_NAME, ""))
        except (TypeError, ValueError):
            active_profile_id = None

    response = TEMPLATES.TemplateResponse(
        request,
        "login.html",
        _login_template_context(
            request,
            profiles,
            active_profile_id=active_profile_id,
            default_profile_id=default_profile_id,
            unlocked=unlocked_state,
        ),
    )
    if active_profile_id is not None:
        ensure_profile_cookie(request, response, db)
    return response


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    profile_id: Optional[int] = Form(default=None, ge=1),
    access_key: Optional[str] = Form(default=None, max_length=128),
    passcode: Optional[str] = Form(default=None, max_length=128),
    db: Session = Depends(get_db),
):
    wants_json = _wants_json(request)
    profiles = get_profiles(db)
    profile_by_id = {profile.id: profile for profile in profiles if profile.id is not None}
    profile = profile_by_id.get(profile_id) if profile_id is not None else None

    credentials_required = not settings.disable_auth
    if credentials_required and not _credentials_available(db, profiles):
        message = "Login credentials are not configured."
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": message},
            )
        return _render_login_error(
            request,
            profiles,
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            credentials_unavailable=True,
        )

    unlock_profile_id: int | None = None
    if credentials_required:
        unlock_profile_id = _credentials_match(
            db,
            profiles,
            access_key=access_key,
            passcode=passcode,
        )
        if unlock_profile_id is None:
            unlock_profile_id = _parse_unlock_token(request.cookies.get(UNLOCK_COOKIE_NAME, ""))

    if credentials_required and unlock_profile_id is None:
        message = "Invalid login credentials."
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": message},
            )
        return _render_login_error(
            request,
            profiles,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not profile:
        if profile_id is None:
            if wants_json:
                response = JSONResponse(status_code=status.HTTP_200_OK, content={"unlocked": True})
            else:
                response = RedirectResponse(
                    url="/login?unlocked=1",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
            if credentials_required:
                response.set_cookie(
                    UNLOCK_COOKIE_NAME,
                    _create_unlock_token(unlock_profile_id if unlock_profile_id else None),
                    max_age=UNLOCK_TTL_SECONDS,
                    httponly=True,
                    samesite="lax",
                    secure=request.url.scheme == "https",
                )
            return response
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Unknown profile."},
            )
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            _login_template_context(
                request,
                profiles,
                error="Unknown profile.",
                unlocked=True,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if credentials_required and unlock_profile_id not in (0, profile.id):
        message = "Login credentials do not allow that profile."
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": message},
            )
        return _render_login_error(
            request,
            profiles,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )

    ttl_seconds = settings.login_session_ttl_hours * 60 * 60
    token = create_session_token(
        profile.id,
        secret=get_session_secret(settings.login_session_secret),
        ttl_seconds=ttl_seconds,
    )
    if wants_json:
        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"ok": True, "redirect_url": "/ui/movies"},
        )
    else:
        response = RedirectResponse(url="/ui/movies", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    set_active_profile_cookie(response, profile.id)
    response.delete_cookie(UNLOCK_COOKIE_NAME)
    return response


@router.post("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(UNLOCK_COOKIE_NAME)
    response.delete_cookie(PROFILE_COOKIE_NAME)
    response.delete_cookie(FILTER_COOKIE_NAME, path=FILTER_COOKIE_PATH)
    return response
