from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.services.movies_detail import get_first_movie_id, get_movie_detail, get_review_neighbors
from api.services.profiles import (
    ensure_profile_cookie,
    get_active_profile_id,
    get_preferences_for_movies,
    get_profiles,
)
from api.services.ui.spotlight import build_spotlight_reason, get_daily_spotlight_ids
from api.services.ui.templates import TEMPLATES

router = APIRouter()


@router.get("/ui/movies/review")
def start_review(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    first_id = get_first_movie_id(db)
    if first_id is None:
        return RedirectResponse(url="/ui/movies", status_code=302)
    return RedirectResponse(url=f"/ui/movies/{first_id}?review=1", status_code=302)


@router.get("/ui/movies/{movie_id}", response_class=HTMLResponse)
def movie_detail(
    movie_id: int,
    request: Request,
    review: bool = Query(default=False),
    spotlight: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        return TEMPLATES.TemplateResponse(
            request,
            "movie_detail.html",
            {
                "movie": None,
                "roles": [],
                "similar": [],
                "spotlight_reason": None,
                "review_mode": False,
                "review_prev_id": None,
                "review_next_id": None,
                "profiles": get_profiles(db),
                "active_profile_id": get_active_profile_id(request, db),
            },
            status_code=404,
        )

    spotlight_reason = None
    spotlight_ids = get_daily_spotlight_ids(db, limit=4)
    if detail.id in spotlight_ids or spotlight:
        spotlight_reason = build_spotlight_reason(detail)

    review_prev_id = None
    review_next_id = None
    if review:
        review_prev_id, review_next_id = get_review_neighbors(db, detail.id)

    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    preferences = get_preferences_for_movies(db, active_profile_id, [detail.id])
    pref = preferences.get(detail.id, {})

    response = TEMPLATES.TemplateResponse(
        request,
        "movie_detail.html",
        {
            "movie": detail,
            "roles": detail.roles,
            "similar": detail.similar,
            "spotlight_reason": spotlight_reason,
            "review_mode": review,
            "review_prev_id": review_prev_id,
            "review_next_id": review_next_id,
            "profiles": profiles,
            "active_profile_id": active_profile_id,
            "movie_liked": pref.get("liked", False),
            "movie_watchlist": pref.get("watchlist", False),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response
