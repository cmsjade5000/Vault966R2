from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.services.movies_detail import get_movie_detail, get_review_neighbors
from api.services.profiles import (
    ensure_profile_cookie,
    get_active_profile_id,
    get_preferences_for_movies,
    get_profiles,
)
from api.services.ui.spotlight import build_spotlight_reason, get_daily_spotlight_ids
from api.services.ui.templates import TEMPLATES
from api.services.source_sync import source_provenance_for_movie
from api.services.trusted_movies import get_untrusted_movie_ids

router = APIRouter()


def _primary_genre(label_list: list[str]) -> str:
    for label in label_list:
        text = label.strip()
        if text:
            return text.lower()
    return ""


def _pick_diverse(similar, *, limit: int, used_ids: set[int]) -> list:
    picks: list = []
    used_genres: set[str] = set()

    for item in similar:
        if len(picks) >= limit:
            break
        if item.id in used_ids:
            continue
        primary = _primary_genre(getattr(item, "genres", []) or [])
        if primary and primary in used_genres:
            continue
        picks.append(item)
        used_ids.add(item.id)
        if primary:
            used_genres.add(primary)

    if len(picks) >= limit:
        return picks

    for item in similar:
        if len(picks) >= limit:
            break
        if item.id in used_ids:
            continue
        picks.append(item)
        used_ids.add(item.id)

    return picks


def _build_reason_tags(base_genres: list[str], base_year: int | None, item) -> list[str]:
    tags: list[str] = []
    base_set = {label.lower() for label in base_genres if label}
    item_genres = [label for label in getattr(item, "genres", []) if label]
    shared = [label for label in item_genres if label.lower() in base_set]
    if shared:
        tags.append(shared[0])
    elif item_genres:
        tags.append(item_genres[0])

    imdb_rating = getattr(item, "imdb_rating", None)
    if isinstance(imdb_rating, (int, float)) and imdb_rating >= 8.0:
        tags.append(f"IMDb {imdb_rating:.1f}")

    if len(tags) < 2:
        rt_score = getattr(item, "rt_score", None)
        if isinstance(rt_score, (int, float)) and rt_score >= 90:
            tags.append(f"RT {int(rt_score)}%")

    if len(tags) < 2 and base_year and getattr(item, "year", None):
        if abs(base_year - item.year) <= 5:  # type: ignore[operator]
            tags.append("Same era")

    return tags[:2]


@router.get("/ui/movies/review")
def start_review(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    return RedirectResponse(url="/ui/review", status_code=302)


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
                "similar_preferences": {},
                "spotlight_reason": None,
                "review_mode": False,
                "review_prev_id": None,
                "review_next_id": None,
                "profiles": get_profiles(db),
                "active_profile_id": get_active_profile_id(request, db),
                "source_provenance": None,
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
    untrusted_ids = get_untrusted_movie_ids(db)
    similar_list = [item for item in (detail.similar or []) if item.id not in untrusted_ids]
    used_ids: set[int] = set()
    pair_with = _pick_diverse(similar_list, limit=2, used_ids=used_ids)
    more_like = _pick_diverse(similar_list, limit=6, used_ids=used_ids)

    preference_ids = [detail.id] + [item.id for item in pair_with + more_like if item.id]
    preferences = get_preferences_for_movies(db, active_profile_id, preference_ids)
    pref = preferences.get(detail.id, {})
    similar_preferences = {
        item_id: preferences.get(item_id, {}) for item_id in preference_ids if item_id != detail.id
    }
    similar_reasons = {
        item.id: _build_reason_tags(detail.genres, detail.year, item)
        for item in pair_with + more_like
        if item.id
    }

    response = TEMPLATES.TemplateResponse(
        request,
        "movie_detail.html",
        {
            "movie": detail,
            "roles": detail.roles,
            "similar": similar_list,
            "spotlight_reason": spotlight_reason,
            "review_mode": review,
            "review_prev_id": review_prev_id,
            "review_next_id": review_next_id,
            "profiles": profiles,
            "active_profile_id": active_profile_id,
            "movie_liked": pref.get("liked", False),
            "movie_watchlist": pref.get("watchlist", False),
            "similar_preferences": similar_preferences,
            "similar_reasons": similar_reasons,
            "pair_with": pair_with,
            "more_like": more_like,
            "source_provenance": source_provenance_for_movie(db, detail.id),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response
