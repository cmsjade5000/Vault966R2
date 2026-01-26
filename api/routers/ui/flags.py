from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from api.db import get_db
from api.deps.auth import require_profile_role
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.profiles import (
    ROLE_ADMIN,
    ensure_profile_cookie,
    get_active_profile_id,
    get_profiles,
)
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])


@router.get("/ui/flags", response_class=HTMLResponse)
def list_flags_ui(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    flags = (
        db.query(MovieFlag)
        .options(joinedload(MovieFlag.movie).joinedload(Movie.genres))
        .order_by(desc(MovieFlag.updated_at))
        .all()
    )
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    response = TEMPLATES.TemplateResponse(
        request,
        "flags.html",
        {
            "flags": flags,
            "profiles": profiles,
            "active_profile_id": active_profile_id,
        },
    )
    ensure_profile_cookie(request, response, db)
    return response
