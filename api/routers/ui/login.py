from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.models.movie import Movie
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
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH
from api.services.ui.templates import TEMPLATES

router = APIRouter()

PROFILE_PICKER_LABELS = ("CORY", "DAMIAN")


def _session_profile_id(request: Request) -> Optional[int]:
    secret = get_session_secret(settings.login_session_secret)
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    session = parse_session_token(token, secret=secret)
    if session:
        return session.profile_id
    return None


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


def _profile_picker_options(profiles) -> list[dict[str, int | str]]:
    options = []
    for index, profile in enumerate(profiles[:2]):
        if profile.id is None:
            continue
        label = PROFILE_PICKER_LABELS[index] if index < len(PROFILE_PICKER_LABELS) else profile.name
        options.append({"id": profile.id, "label": label})
    return options


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
        return RedirectResponse(url="/ui/movies", status_code=status.HTTP_302_FOUND)

    active_profile_id = None
    if request.cookies.get(PROFILE_COOKIE_NAME):
        try:
            active_profile_id = int(request.cookies.get(PROFILE_COOKIE_NAME, ""))
        except (TypeError, ValueError):
            active_profile_id = None

    archive_poster_urls = _archive_poster_urls(db)
    archive_tiles = _archive_tiles(archive_poster_urls)

    response = TEMPLATES.TemplateResponse(
        request,
        "login.html",
        {
            "profiles": profiles,
            "active_profile_id": active_profile_id,
            "error": None,
            "unlocked": unlocked_state,
            "default_profile_id": default_profile_id,
            "profile_options": _profile_picker_options(profiles),
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
    profile_id: Optional[int] = Form(default=None, ge=1),
    db: Session = Depends(get_db),
):
    wants_json = _wants_json(request)
    profiles = get_profiles(db)
    profile_by_id = {profile.id: profile for profile in profiles if profile.id is not None}
    profile = profile_by_id.get(profile_id) if profile_id is not None else None
    if not profile:
        if profile_id is None:
            if wants_json:
                return JSONResponse(status_code=status.HTTP_200_OK, content={"unlocked": True})
            return RedirectResponse(url="/login?unlocked=1", status_code=status.HTTP_303_SEE_OTHER)
        if wants_json:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Unknown profile."},
            )
        archive_poster_urls = _archive_poster_urls(db)
        archive_tiles = _archive_tiles(archive_poster_urls)
        return TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "profiles": profiles,
                "active_profile_id": None,
                "error": "Unknown profile.",
                "unlocked": True,
                "default_profile_id": None,
                "profile_options": _profile_picker_options(profiles),
                "archive_tiles": archive_tiles,
                "archive_poster_urls": archive_poster_urls,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
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
    return response


@router.post("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(PROFILE_COOKIE_NAME)
    response.delete_cookie(FILTER_COOKIE_NAME, path=FILTER_COOKIE_PATH)
    return response
