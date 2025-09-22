from __future__ import annotations

import pathlib
import random
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.flic_preset import FlicPreset
from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.services.movies_detail import get_movie_detail
from core.picker import calculate_flic_score
from api.utils.query_params import parse_optional_non_negative_int

TEMPLATES = Jinja2Templates(
    directory=str(pathlib.Path(__file__).resolve().parents[2] / "templates")
)

router = APIRouter(tags=["ui"])


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_filters(
    query,
    *,
    q: Optional[str],
    genres: Optional[str],
    moods: Optional[str],
    year_min: Optional[int],
    year_max: Optional[int],
    runtime_max: Optional[int],
):
    if q:
        query = query.filter(Movie.title.ilike(f"%{q.strip()}%"))
    for name in _parse_csv(genres):
        query = query.filter(Movie.genres.any(Genre.name == name))
    for name in _parse_csv(moods):
        query = query.filter(Movie.moods.any(Mood.name == name))
    if year_min is not None:
        query = query.filter(Movie.year >= year_min)
    if year_max is not None:
        query = query.filter(Movie.year <= year_max)
    if runtime_max is not None:
        query = query.filter(Movie.runtime <= runtime_max)
    return query


@router.get("/ui/movies", response_class=HTMLResponse)
def movies_grid(
    request: Request,
    q: Optional[str] = Query(default=None),
    genres: Optional[str] = Query(default=None),
    moods: Optional[str] = Query(default=None),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    order_by: str = Query(default="title_asc"),
    db: Session = Depends(get_db),
):
    year_min = parse_optional_non_negative_int(year_min, "year_min")
    year_max = parse_optional_non_negative_int(year_max, "year_max")
    runtime_max = parse_optional_non_negative_int(runtime_max, "runtime_max")

    filtered_query = _apply_filters(
        db.query(Movie),
        q=q,
        genres=genres,
        moods=moods,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    )
    total = filtered_query.with_entities(func.count(Movie.id)).scalar() or 0
    avg_year_value = filtered_query.with_entities(func.avg(Movie.year)).scalar()
    avg_year = int(round(avg_year_value)) if avg_year_value else None

    filtered_ids = _apply_filters(
        db.query(Movie.id),
        q=q,
        genres=genres,
        moods=moods,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    ).subquery()

    top_genre = (
        db.query(Genre.name, func.count().label("count"))
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(filtered_ids, filtered_ids.c.id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .order_by(func.count().desc())
        .first()
    )

    top_mood = (
        db.query(Mood.name, func.count().label("count"))
        .join(movie_moods, Mood.id == movie_moods.c.mood_id)
        .join(filtered_ids, filtered_ids.c.id == movie_moods.c.movie_id)
        .group_by(Mood.name)
        .order_by(func.count().desc())
        .first()
    )

    stats = {
        "total": total,
        "average_year": avg_year,
        "top_genre": top_genre[0] if top_genre else "—",
        "top_mood": top_mood[0] if top_mood else "—",
    }

    taglines = [
        "Your movie buddy—let’s find a vibe.",
        "Shortlist in two taps.",
        "Prefer surprises? I’ve got you.",
    ]
    initial_tagline = random.choice(taglines)

    built_in_presets = [
        {
            "name": "Rainy Night",
            "filters": {"moods": ["Moody"]},
        },
        {
            "name": "90-min Comfort",
            "filters": {"runtime_max": 95},
        },
    ]

    user_presets = db.query(FlicPreset).order_by(FlicPreset.created_at.desc()).all()
    serialized_presets = [
        {
            "id": preset.id,
            "name": preset.name,
            "filters": preset.filters,
        }
        for preset in user_presets
    ]

    page_size = 30
    if total == 0:
        total_pages = 0
        page = 1
        offset = 0
        movies: List[Movie] = []
    else:
        total_pages = (total + page_size - 1) // page_size
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * page_size
        if order_by == "flic":
            all_movies = filtered_query.options(
                selectinload(Movie.genres), selectinload(Movie.moods)
            ).all()
            filters = {
                "genres": _parse_csv(genres),
                "moods": _parse_csv(moods),
                "runtime_max": runtime_max,
                "year_min": year_min,
                "year_max": year_max,
            }
            scored = []
            for movie in all_movies:
                candidate = {
                    "genres": [g.name for g in movie.genres],
                    "moods": [m.name for m in movie.moods],
                    "runtime": movie.runtime,
                    "year": movie.year,
                }
                score, _ = calculate_flic_score(candidate, filters)
                scored.append((score, movie))

            scored.sort(key=lambda item: item[0], reverse=True)
            paginated = scored[offset : offset + page_size]
            movies = [movie for _, movie in paginated]
        else:
            ordering_map = {
                "title_asc": Movie.title.asc(),
                "title_desc": Movie.title.desc(),
                "year_desc": Movie.year.desc(),
                "runtime_asc": Movie.runtime.asc(),
            }
            sort_clause = ordering_map.get(order_by, Movie.title.asc())
            movies = (
                filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                .order_by(sort_clause)
                .offset(offset)
                .limit(page_size)
                .all()
            )

    return TEMPLATES.TemplateResponse(
        "movies_grid.html",
        {
            "request": request,
            "movies": movies,
            "q": q,
            "genres": genres,
            "moods": moods,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "page_size": page_size,
            "stats": stats,
            "taglines": taglines,
            "initial_tagline": initial_tagline,
            "built_in_presets": built_in_presets,
            "user_presets": serialized_presets,
            "year_min": year_min,
            "year_max": year_max,
            "runtime_max": runtime_max,
            "order_by": order_by,
        },
    )


@router.get("/ui/movies/{movie_id}", response_class=HTMLResponse)
def movie_detail(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        return TEMPLATES.TemplateResponse(
            "movie_detail.html",
            {
                "request": request,
                "movie": None,
                "roles": [],
                "similar": [],
            },
            status_code=404,
        )

    return TEMPLATES.TemplateResponse(
        "movie_detail.html",
        {
            "request": request,
            "movie": detail,
            "roles": detail.roles,
            "similar": detail.similar,
        },
    )
