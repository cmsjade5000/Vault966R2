from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import random
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.deps.auth import require_strict_same_origin
from api.models.profile import Profile
from api.schemas.common import SEE_OTHER_REDIRECT_RESPONSES
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
    personal_sign_in_only,
    setup_record,
)
from api.services.login_throttle import LoginAttemptLimiter
from api.services.login_posters import login_posters
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH
from api.services.ui.templates import TEMPLATES

router = APIRouter()
login_attempt_limiter = LoginAttemptLimiter()

PROFILE_PICKER_LABELS = ("User A", "User B")
UNLOCK_COOKIE_NAME = "vault_unlock"
UNLOCK_TOKEN_VERSION = 1
UNLOCK_TTL_SECONDS = 5 * 60


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(payload: str) -> str:
    secret = get_session_secret(settings.login_session_secret)
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _create_unlock_token(profile_id: int | None, revision: int = 0) -> str:
    now = int(time.time())
    payload = {
        "v": UNLOCK_TOKEN_VERSION,
        "profile_id": profile_id,
        "revision": revision,
        "iat": now,
        "exp": now + UNLOCK_TTL_SECONDS,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64encode(payload_raw)
    return f"{payload_b64}.{_sign(payload_b64)}"


def _parse_unlock_token(token: str, expected_revision: int = 0) -> int | None:
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
        revision = int(payload.get("revision", 0))
    except (TypeError, ValueError):
        return None
    if revision != expected_revision or expires_at <= int(time.time()):
        return None
    raw_profile_id = payload.get("profile_id")
    if raw_profile_id is None:
        return 0
    try:
        profile_id = int(raw_profile_id)
    except (TypeError, ValueError):
        return None
    return profile_id if profile_id > 0 else None


def _unlock_revision(db: Session) -> int:
    record = setup_record(db)
    return record.unlock_revision if record else 0


def _session_profile_id(request: Request, db: Session) -> Optional[int]:
    secret = get_session_secret(settings.login_session_secret)
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    session = parse_session_token(token, secret=secret)
    if session:
        profile = db.get(Profile, session.profile_id)
        if profile and profile.archived_at is None and profile.session_revision == session.revision:
            return session.profile_id
    return None


def _public_archive_posters(request: Request) -> list[dict]:
    try:
        posters = login_posters()
    except (OSError, ValueError, KeyError, TypeError):
        # Decorative artwork must never prevent signing in.
        return []
    return [
        {
            **poster,
            "url": f"{request.url_for('static', path=poster['path'])}?v={poster['sha256'][:12]}",
        }
        for poster in posters
    ]


def _archive_tiles(posters: list[dict], *, limit: int = 12) -> list[Optional[dict]]:
    tiles: list[Optional[dict]] = list(posters[:limit])
    if len(tiles) < limit:
        tiles.extend([None] * (limit - len(tiles)))
    return tiles


def _wants_json(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept


def _login_client_key(request: Request) -> str | None:
    """Return the ASGI/Uvicorn-derived client address without inspecting headers."""
    if request.client is None or not request.client.host:
        return None
    return request.client.host


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
    return db_credentials_configured(db) or (
        not personal_sign_in_only(db) and _login_credentials_configured(profiles)
    )


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
    if personal_sign_in_only(db):
        return None
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
    switching: bool = False,
) -> dict:
    archive_posters = _public_archive_posters(request)
    random.SystemRandom().shuffle(archive_posters)
    return {
        "switching": switching,
        "form_action": "/ui/switch-person" if switching else "/login",
        "profiles": profiles,
        "active_profile_id": active_profile_id,
        "error": error,
        "unlocked": unlocked,
        "credentials_unavailable": credentials_unavailable,
        "default_profile_id": default_profile_id,
        "profile_options": _profile_picker_options(profiles),
        "archive_tiles": _archive_tiles(archive_posters),
        "archive_poster_urls": [poster["url"] for poster in archive_posters],
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
            switching=request.url.path == "/ui/switch-person",
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

    unlocked_state = (
        bool(unlocked)
        and not personal_sign_in_only(db)
        and _parse_unlock_token(request.cookies.get(UNLOCK_COOKIE_NAME, ""), _unlock_revision(db))
        == 0
    )
    if _session_profile_id(request, db) and not unlocked_state:
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
            [] if personal_sign_in_only(db) else profiles,
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
    _: None = Depends(require_strict_same_origin),
):
    wants_json = _wants_json(request)
    switching = request.url.path == "/ui/switch-person"
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
    client_key = _login_client_key(request) if credentials_required else None
    if credentials_required:
        # A signed unlock token is already a valid credential.  Preserve the
        # profile-selection step without routing it through failed-attempt
        # throttling.
        unlock_profile_id = (
            None
            if switching or personal_sign_in_only(db)
            else _parse_unlock_token(
                request.cookies.get(UNLOCK_COOKIE_NAME, ""), _unlock_revision(db)
            )
        )
        if unlock_profile_id is None:
            if client_key is None or not login_attempt_limiter.begin_attempt(client_key):
                message = "Too many login attempts. Please try again later."
                if wants_json:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={"error": message},
                    )
                return _render_login_error(
                    request,
                    profiles,
                    message=message,
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            try:
                unlock_profile_id = _credentials_match(
                    db,
                    profiles,
                    access_key=access_key,
                    passcode=passcode,
                )
            except Exception:
                login_attempt_limiter.cancel_attempt(client_key)
                raise
            if unlock_profile_id is None:
                login_attempt_limiter.record_failure(client_key)

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

    if credentials_required and client_key is not None:
        login_attempt_limiter.clear(client_key)

    if profile_id is None and unlock_profile_id and unlock_profile_id > 0:
        profile = profile_by_id.get(unlock_profile_id)
    if switching and unlock_profile_id == 0:
        return (
            JSONResponse(
                status_code=403, content={"error": "Use personal credentials to switch person."}
            )
            if wants_json
            else _render_login_error(
                request,
                profiles,
                message="Use personal credentials to switch person.",
                status_code=403,
            )
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
                    _create_unlock_token(
                        unlock_profile_id if unlock_profile_id else None, _unlock_revision(db)
                    ),
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
        revision=profile.session_revision,
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
    if switching:
        response.delete_cookie(FILTER_COOKIE_NAME, path=FILTER_COOKIE_PATH)
    return response


@router.post(
    "/logout",
    status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse,
    responses=SEE_OTHER_REDIRECT_RESPONSES,
)
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(UNLOCK_COOKIE_NAME)
    response.delete_cookie(PROFILE_COOKIE_NAME)
    response.delete_cookie(FILTER_COOKIE_NAME, path=FILTER_COOKIE_PATH)
    return response


@router.get("/ui/switch-person", response_class=HTMLResponse)
def switch_person_ui(request: Request, db: Session = Depends(get_db)):
    return TEMPLATES.TemplateResponse(
        request, "login.html", _login_template_context(request, [], switching=True)
    )


@router.post("/ui/switch-person", response_class=HTMLResponse)
def switch_person_submit(
    request: Request,
    access_key: Optional[str] = Form(default=None, max_length=128),
    passcode: Optional[str] = Form(default=None, max_length=128),
    db: Session = Depends(get_db),
    _: None = Depends(require_strict_same_origin),
):
    return login_submit(request, profile_id=None, access_key=access_key, passcode=passcode, db=db)
