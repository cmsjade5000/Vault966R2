from __future__ import annotations

from typing import Optional

import hmac

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.models.movie import Movie
from api.services.profiles import (
    PROFILE_COOKIE_NAME,
    ROLE_ADMIN,
    ROLE_REVIEWER,
    ensure_profile_cookie,
    get_profiles,
    set_active_profile_cookie,
)
from api.services.session import SESSION_COOKIE_NAME, create_session_token, parse_session_token
from api.services.ui.templates import TEMPLATES

router = APIRouter()

ACCESS_KEY_MAX_LENGTH = 64
PASSCODE_MAX_LENGTH = 128


def _login_configured() -> bool:
    if not settings.login_session_secret:
        return False
    if settings.login_access_key_user_a and settings.login_passcode_user_a:
        return True
    if settings.login_access_key_user_b and settings.login_passcode_user_b:
        return True
    return bool(settings.login_access_key and settings.login_passcode)


def _validate_access_key(value: Optional[str]) -> bool:
    if value is None:
        return False
    clean = value.strip()
    if not (3 <= len(clean) <= ACCESS_KEY_MAX_LENGTH):
        return False
    return all(char.isalnum() or char in {"-", "_", "."} for char in clean)


def _validate_passcode(value: Optional[str]) -> bool:
    if value is None:
        return False
    if not (4 <= len(value) <= PASSCODE_MAX_LENGTH):
        return False
    return all(32 <= ord(char) <= 126 for char in value)


def _session_profile_id(request: Request) -> Optional[int]:
    secret = settings.login_session_secret
    if not secret:
        return None
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    session = parse_session_token(token, secret=secret)
    if session:
        return session.profile_id
    return None


def _profile_lookup(profiles):
    return {profile.id: profile for profile in profiles if profile.id is not None}


def _archive_poster_urls(db: Session, *, limit: int = 36) -> list[str]:
    rows = (
        db.query(Movie.poster_url)
        .filter(Movie.poster_url.isnot(None))
        .order_by(func.random())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row[0]]


def _archive_tiles(urls: list[str], *, limit: int = 12) -> list[Optional[str]]:
    tiles: list[Optional[str]] = list(urls[:limit])
    if len(tiles) < limit:
        tiles.extend([None] * (limit - len(tiles)))
    return tiles


def _wants_json(request: Request) -> bool:
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept


def _resolve_profile(
    profiles: list,
    *,
    role: str,
    name_fallback: str,
) -> Optional[object]:
    for profile in profiles:
        if getattr(profile, "role", None) == role:
            return profile
    for profile in profiles:
        if getattr(profile, "name", None) == name_fallback:
            return profile
    return profiles[0] if profiles else None


def _credential_pairs():
    pairs = []
    if settings.login_access_key_user_a and settings.login_passcode_user_a:
        pairs.append(
            (
                ROLE_ADMIN,
                "User A",
                settings.login_access_key_user_a,
                settings.login_passcode_user_a,
            )
        )
    if settings.login_access_key_user_b and settings.login_passcode_user_b:
        pairs.append(
            (
                ROLE_REVIEWER,
                "User B",
                settings.login_access_key_user_b,
                settings.login_passcode_user_b,
            )
        )
    if pairs:
        return pairs
    if settings.login_access_key and settings.login_passcode:
        pairs.append(
            (
                ROLE_ADMIN,
                "User A",
                settings.login_access_key,
                settings.login_passcode,
            )
        )
    return pairs


def _match_profile_for_credentials(
    profiles: list,
    *,
    access_key: str,
    passcode: str,
):
    for role, name_fallback, key, code in _credential_pairs():
        if hmac.compare_digest(access_key, key) and hmac.compare_digest(passcode, code):
            return _resolve_profile(profiles, role=role, name_fallback=name_fallback)
    return None


@router.get("/login", response_class=HTMLResponse)
def login(
    request: Request,
    unlocked: Optional[int] = Query(default=None, ge=0, le=1),
    db: Session = Depends(get_db),
):
    """Public login landing page (no auth required)."""
    profiles = get_profiles(db)
    default_profile_id = profiles[0].id if profiles else None

    unlocked_state = bool(unlocked)
    if _session_profile_id(request) and not unlocked_state:
        return RedirectResponse(url="/ui/discover", status_code=status.HTTP_302_FOUND)

    active_profile_id = None
    if request.cookies.get(PROFILE_COOKIE_NAME):
        try:
            active_profile_id = int(request.cookies.get(PROFILE_COOKIE_NAME, ""))
        except (TypeError, ValueError):
            active_profile_id = None

    error = None
    if not _login_configured():
        error = "Login is not configured yet."

    archive_poster_urls = _archive_poster_urls(db)
    archive_tiles = _archive_tiles(archive_poster_urls)

    response = TEMPLATES.TemplateResponse(
        request,
        "login.html",
        {
            "profiles": profiles,
            "active_profile_id": active_profile_id,
            "error": error,
            "unlocked": unlocked_state,
            "default_profile_id": default_profile_id,
            "archive_tiles": archive_tiles,
            "archive_poster_urls": archive_poster_urls,
        },
    )
    if active_profile_id is not None:
        ensure_profile_cookie(request, response, db)
    return response


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    access_key: str = Form(..., max_length=ACCESS_KEY_MAX_LENGTH),
    passcode: str = Form(..., max_length=PASSCODE_MAX_LENGTH),
    db: Session = Depends(get_db),
):
    wants_json = _wants_json(request)
    profiles = get_profiles(db)
    default_profile_id = profiles[0].id if profiles else None

    if not _login_configured():
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "Login is not configured yet."},
            )
        archive_poster_urls = _archive_poster_urls(db)
        archive_tiles = _archive_tiles(archive_poster_urls)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "profiles": profiles,
                "active_profile_id": None,
                "error": "Login is not configured yet.",
                "unlocked": False,
                "default_profile_id": default_profile_id,
                "archive_tiles": archive_tiles,
                "archive_poster_urls": archive_poster_urls,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    clean_access_key = access_key.strip()
    if not _validate_access_key(clean_access_key) or not _validate_passcode(passcode):
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid credentials."},
            )
        archive_poster_urls = _archive_poster_urls(db)
        archive_tiles = _archive_tiles(archive_poster_urls)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "profiles": profiles,
                "active_profile_id": None,
                "error": "Invalid credentials.",
                "unlocked": False,
                "default_profile_id": default_profile_id,
                "archive_tiles": archive_tiles,
                "archive_poster_urls": archive_poster_urls,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    profile = _match_profile_for_credentials(
        profiles,
        access_key=clean_access_key,
        passcode=passcode,
    )
    if not profile:
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid credentials."},
            )
        archive_poster_urls = _archive_poster_urls(db)
        archive_tiles = _archive_tiles(archive_poster_urls)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "profiles": profiles,
                "active_profile_id": None,
                "error": "Invalid credentials.",
                "unlocked": False,
                "default_profile_id": default_profile_id,
                "archive_tiles": archive_tiles,
                "archive_poster_urls": archive_poster_urls,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    ttl_seconds = settings.login_session_ttl_hours * 60 * 60
    token = create_session_token(
        profile.id, secret=settings.login_session_secret, ttl_seconds=ttl_seconds
    )
    if wants_json:
        response = JSONResponse(status_code=status.HTTP_200_OK, content={"ok": True})
    else:
        response = RedirectResponse(url="/login?unlocked=1", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    set_active_profile_cookie(response, profile.id)
    return response


@router.post("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(PROFILE_COOKIE_NAME)
    return response
