from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.movie import Movie
from api.services.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from api.services.movies_curated import get_collection_health, get_curated_collections
from api.services.ui.grid import (
    FILTER_COOKIE_MAX_AGE,
    FILTER_COOKIE_NAME,
    attach_poster_themes,
    dump_filter_cookie,
    get_built_in_presets,
    get_decade_options,
    get_genre_options,
    get_runtime_presets,
    get_taglines,
    load_filter_cookie,
    query_library_stats,
    serialize_user_presets,
)
from api.services.ui.templates import TEMPLATES
from core.genres import split_and_normalize
from core.picker import calculate_flic_score

router = APIRouter()


@router.get("/ui/movies", response_class=HTMLResponse)
def movies_grid(
    request: Request,
    q: Optional[str] = Query(default=None),
    genres: Optional[str] = Query(default=None),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    order_by: str = Query(default="title_asc"),
    db: Session = Depends(get_db),
):
    cookie_data = load_filter_cookie(request)
    using_query = bool(request.query_params)

    def resolve(source_value, key):
        return source_value if using_query else cookie_data.get(key)

    params: MovieFilterParams = parse_movie_filters(
        q=resolve(q, "q"),
        year_min=resolve(year_min, "year_min"),
        year_max=resolve(year_max, "year_max"),
        runtime_min=resolve(None, "runtime_min"),
        runtime_max=resolve(runtime_max, "runtime_max"),
        genres=resolve(genres, "genres"),
        moods=resolve(None, "moods"),
        order_by=resolve(order_by, "order_by"),
    )

    current_page = page
    if not using_query:
        cookie_page = cookie_data.get("page")
        if cookie_page is not None:
            try:
                current_page = int(cookie_page)
            except (TypeError, ValueError):
                current_page = page
    if current_page < 1:
        current_page = 1

    base_query = db.query(Movie)
    filtered_query = apply_filters(base_query, params)
    total = filtered_query.with_entities(func.count(Movie.id)).scalar() or 0

    stats = query_library_stats(db)
    taglines, initial_tagline = get_taglines()
    built_in_presets = get_built_in_presets()
    user_presets = serialize_user_presets(db)
    genre_options = get_genre_options(db)
    decade_options = get_decade_options(db)
    runtime_presets = get_runtime_presets()

    page_size = 30
    if total == 0:
        total_pages = 0
        current_page = 1
        offset = 0
        movies: list[Movie] = []
    else:
        total_pages = (total + page_size - 1) // page_size
        current_page = min(max(current_page, 1), total_pages)
        offset = (current_page - 1) * page_size
        if params.order_by == "flic":
            all_movies = filtered_query.options(
                selectinload(Movie.genres), selectinload(Movie.moods)
            ).all()
            attach_poster_themes(all_movies)
            filters = {
                "genres": split_and_normalize(params.genres),
                "moods": list(params.moods),
                "runtime_min": params.runtime_min,
                "runtime_max": params.runtime_max,
                "year_min": params.year_min,
                "year_max": params.year_max,
            }
            scored = []
            for movie in all_movies:
                candidate = {
                    "genres": split_and_normalize([g.name for g in movie.genres]),
                    "moods": [m.name for m in movie.moods],
                    "runtime": movie.runtime,
                    "year": movie.year,
                }
                score, _ = calculate_flic_score(candidate, filters)
                scored.append((score, movie))

            scored.sort(key=lambda item: item[0], reverse=True)
            paginated = scored[offset : offset + page_size]
            movies = [movie for _, movie in paginated]
            attach_poster_themes(movies)
        else:
            clause = ordering_clause(params.order_by)
            movies = (
                filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                .order_by(clause)
                .offset(offset)
                .limit(page_size)
                .all()
            )
            attach_poster_themes(movies)

    featured_limit = 12
    featured_movies = movies[:featured_limit]
    table_movies = movies

    carousel_limit = 20
    poster_carousel_movies = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .filter(Movie.poster_url.isnot(None))
        .order_by(func.random())
        .limit(carousel_limit)
        .all()
    )
    attach_poster_themes(poster_carousel_movies)

    curated_collections = get_curated_collections(db)

    genres_value = ", ".join(params.genres)
    runtime_max_value = params.runtime_max if params.runtime_max is not None else ""
    year_min_value = params.year_min if params.year_min is not None else ""
    year_max_value = params.year_max if params.year_max is not None else ""

    context = {
        "request": request,
        "movies": movies,
        "q": params.q,
        "genres": genres_value,
        "page": current_page,
        "total": total,
        "total_pages": total_pages,
        "page_size": page_size,
        "stats": stats,
        "taglines": taglines,
        "initial_tagline": initial_tagline,
        "built_in_presets": built_in_presets,
        "user_presets": user_presets,
        "year_min": year_min_value,
        "year_max": year_max_value,
        "runtime_max": runtime_max_value,
        "order_by": params.order_by,
        "genre_options": genre_options,
        "decade_options": decade_options,
        "runtime_presets": runtime_presets,
        "featured_movies": featured_movies,
        "table_movies": table_movies,
        "featured_limit": featured_limit,
        "poster_carousel_movies": poster_carousel_movies,
        "curated_collections": curated_collections,
    }

    response = TEMPLATES.TemplateResponse("movies_grid.html", context)
    cookie_payload = params.to_cookie_payload(page=current_page)
    response.set_cookie(
        FILTER_COOKIE_NAME,
        dump_filter_cookie(cookie_payload),
        max_age=FILTER_COOKIE_MAX_AGE,
        samesite="lax",
        path="/ui/movies",
    )
    return response


@router.get("/ui/movies/health", response_class=HTMLResponse)
def movies_health(request: Request, db: Session = Depends(get_db)):
    collection_health = get_collection_health(db)
    context = {
        "request": request,
        "collection_health": collection_health,
    }
    return TEMPLATES.TemplateResponse("movies_health.html", context)


@router.get("/ui/movies/collections", response_class=HTMLResponse)
def movies_collections(request: Request, db: Session = Depends(get_db)):
    curated_collections = get_curated_collections(db)
    context = {
        "request": request,
        "curated_collections": curated_collections,
    }
    return TEMPLATES.TemplateResponse("movies_collections.html", context)
