from __future__ import annotations

from typing import Iterable, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.db import get_db
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.movies_curated import get_collection_health
from api.services.ui.grid import (
    FILTER_COOKIE_MAX_AGE,
    FILTER_COOKIE_NAME,
    attach_genre_display,
    attach_poster_themes,
    dump_filter_cookie,
    get_built_in_presets,
    get_decade_options,
    get_genre_options,
    get_mood_options,
    get_runtime_presets,
    get_taglines,
    load_filter_cookie,
    query_library_stats,
    serialize_user_presets,
)
from api.services.ui.spotlight import get_daily_spotlight_movies
from api.services.ui.templates import TEMPLATES
from api.services.double_feature import DEFAULT_DOUBLE_FEATURE_RUNTIME, pick_double_feature
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from api.services.profiles import (
    ensure_profile_cookie,
    get_active_profile_id,
    get_preferences_for_movies,
    get_profiles,
    get_watchlist_movies,
)
from api.services.semantic_search import (
    SemanticSearchError,
    SemanticSearchUnavailable,
    apply_semantic_query_overrides,
    parse_semantic_intent,
    semantic_query_forces_animation,
    semantic_search_enabled,
    semantic_search_movies,
)
from api.utils.sampling import reorder_movies_by_id_sequence, sample_movie_ids
from core.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from core.picker import PickerCandidate, PickerFilters, calculate_flic_score

router = APIRouter()

RANDOM_ORDER_LIMIT = 2000


def _build_flic_filters(params: MovieFilterParams) -> Tuple[PickerFilters, bool]:
    """Return picker filters plus a flag indicating whether defaults were applied."""

    filters = PickerFilters.from_params(params)
    has_inputs = any(
        (
            filters.genres,
            filters.moods,
            filters.runtime_min is not None,
            filters.runtime_max is not None,
            filters.year_min is not None,
            filters.year_max is not None,
        )
    )
    if has_inputs:
        return filters, False

    fallback = PickerFilters.from_values(
        runtime_max=125,
        year_min=1990,
    )
    return fallback, True


def _summarize_flic_filters(filters: PickerFilters, *, used_defaults: bool) -> str:
    parts: list[str] = []
    if filters.genres:
        genre_list = ", ".join(filters.genres[:2])
        if len(filters.genres) > 2:
            genre_list = f"{genre_list}…"
        parts.append(f"Genres: {genre_list}")
    if filters.moods:
        mood_list = ", ".join(filters.moods[:2])
        if len(filters.moods) > 2:
            mood_list = f"{mood_list}…"
        parts.append(f"Moods: {mood_list}")
    if filters.runtime_max is not None:
        parts.append(f"≤ {filters.runtime_max} min")
    if filters.year_min is not None or filters.year_max is not None:
        start = filters.year_min or "Any"
        end = filters.year_max or "Now"
        parts.append(f"Years: {start}–{end}")
    if used_defaults:
        parts.append("Default watch-night heuristics (≤ 2h, 1990+)")
    return " • ".join(parts) if parts else "Default watch-night heuristics (≤ 2h, 1990+)"


def _assign_flic_scores(movies: Iterable[Movie], filters: dict[str, object]) -> None:
    if not movies or not filters:
        return

    for movie in movies:
        try:
            genre_names = [
                getattr(genre, "name", None) or ""
                for genre in getattr(movie, "genres", [])  # type: ignore[arg-type]
            ]
        except TypeError:
            genre_names = []

        try:
            mood_names = [
                getattr(mood, "name", None) or ""
                for mood in getattr(movie, "moods", [])  # type: ignore[arg-type]
            ]
        except TypeError:
            mood_names = []

        candidate = PickerCandidate.from_iterables(
            genres=genre_names,
            moods=mood_names,
            runtime=getattr(movie, "runtime", None),
            year=getattr(movie, "year", None),
        ).to_payload()
        score, _ = calculate_flic_score(candidate, filters)
        setattr(movie, "flic_score", score)


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
    semantic: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
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
        moods=resolve(moods, "moods"),
        order_by=resolve(order_by, "order_by"),
    )

    semantic_value = resolve(semantic, "semantic")
    semantic_active = str(semantic_value).lower() in {"1", "true", "yes", "on"}

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

    semantic_filters = MovieFilterParams(
        q=None,
        year_min=params.year_min,
        year_max=params.year_max,
        runtime_min=params.runtime_min,
        runtime_max=params.runtime_max,
        genres=params.genres,
        moods=params.moods,
        order_by="title_asc",
    )
    semantic_intent = None
    if semantic_active and params.q:
        semantic_filters = apply_semantic_query_overrides(params.q, semantic_filters)
        semantic_intent = parse_semantic_intent(params.q, semantic_filters)
        semantic_filters = semantic_intent.params

    base_query = db.query(Movie)
    filtered_query = apply_filters(base_query, params)
    total = filtered_query.with_entities(func.count(Movie.id)).scalar() or 0

    stats = query_library_stats(db)
    taglines, initial_tagline = get_taglines()
    built_in_presets = get_built_in_presets()
    user_presets = serialize_user_presets(db)
    genre_options = get_genre_options(db)
    mood_options = get_mood_options(db)
    decade_options = get_decade_options(db)
    runtime_presets = get_runtime_presets()

    page_size = 30
    flic_filters_summary = None
    flic_filters_default = False
    flic_rank_offset = 0
    flic_filters_payload: Optional[dict[str, object]] = None

    if total == 0:
        total_pages = 0
        current_page = 1
        offset = 0
        movies: list[Movie] = []
    else:
        total_pages = (total + page_size - 1) // page_size
        current_page = min(max(current_page, 1), total_pages)
        offset = (current_page - 1) * page_size
        if semantic_active and params.q and semantic_search_enabled(db):

            def apply_semantic_filters(queryset):
                return apply_filters(queryset, semantic_filters)

            limit = settings.semantic_search_top_k
            if semantic_query_forces_animation(params.q):
                limit = min(max(limit * 5, 500), 2000)
            try:
                rows, total = semantic_search_movies(
                    db,
                    query=params.q,
                    filtered_query=apply_semantic_filters,
                    limit=limit,
                    page=current_page,
                    page_size=page_size,
                    intent=semantic_intent,
                )
            except (SemanticSearchUnavailable, SemanticSearchError):
                rows = []

            if rows:
                movies = [row[0] for row in rows]
            else:
                semantic_active = False
                total = filtered_query.with_entities(func.count(Movie.id)).scalar() or 0
                total_pages = (total + page_size - 1) // page_size
                current_page = min(max(current_page, 1), total_pages)
                offset = (current_page - 1) * page_size
                clause = ordering_clause(params.order_by)
                movies = (
                    filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                    .order_by(clause)
                    .offset(offset)
                    .limit(page_size)
                    .all()
                )
                attach_poster_themes(movies)
                attach_genre_display(movies)
        elif params.order_by == "flic":
            flic_filters, used_defaults = _build_flic_filters(params)
            flic_filters_default = used_defaults
            flic_filters_payload = flic_filters.to_payload()
            ranked = rank_movie_ids_by_flic(
                db,
                base_query=filtered_query,
                filters=flic_filters_payload,
            )
            total = len(ranked)
            page_ids = [movie_id for _, movie_id in ranked[offset : offset + page_size]]
            score_by_id = {movie_id: score for score, movie_id in ranked}
            movies = fetch_movies_in_rank_order(
                db,
                ranked_ids=page_ids,
                options=[selectinload(Movie.genres), selectinload(Movie.moods)],
            )
            for movie in movies:
                if movie.id is not None:
                    setattr(movie, "flic_score", score_by_id.get(movie.id, float("-inf")))
            attach_poster_themes(movies)
            attach_genre_display(movies)
            flic_rank_offset = offset
            flic_filters_summary = _summarize_flic_filters(
                flic_filters, used_defaults=used_defaults
            )
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
            attach_genre_display(movies)

    featured_row_size = 4
    featured_rows = 3
    featured_limit = featured_row_size * featured_rows
    featured_movies: list[Movie] = []
    featured_query = (
        apply_filters(base_query, semantic_filters)
        if semantic_active and params.q
        else filtered_query
    )
    if total:
        if total <= RANDOM_ORDER_LIMIT:
            base_featured = (
                featured_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                .order_by(func.random())
                .limit(featured_limit)
                .all()
            )
        else:
            featured_ids = sample_movie_ids(featured_query, total=total, limit=featured_limit)
            base_featured_raw = (
                db.query(Movie)
                .options(selectinload(Movie.genres), selectinload(Movie.moods))
                .filter(Movie.id.in_(featured_ids))
                .all()
            )
            base_featured = reorder_movies_by_id_sequence(base_featured_raw, featured_ids)
        featured_movies.extend(base_featured)
        featured_ids = {movie.id for movie in featured_movies if movie.id is not None}
        filler_needed = (
            featured_row_size - (len(featured_movies) % featured_row_size)
        ) % featured_row_size

        if filler_needed:
            filler_movies: list[Movie] = []

            def _append_candidate(candidate: Movie) -> bool:
                if not candidate or candidate.id is None:
                    return False
                if candidate.id in featured_ids:
                    return False
                featured_ids.add(candidate.id)
                filler_movies.append(candidate)
                return len(filler_movies) >= filler_needed

            for movie in movies:
                if _append_candidate(movie):
                    break

            if len(filler_movies) < filler_needed:
                extra_needed = filler_needed - len(filler_movies)
                extra_query = featured_query
                if featured_ids:
                    extra_query = extra_query.filter(~Movie.id.in_(list(featured_ids)))
                extra_total = extra_query.with_entities(func.count(Movie.id)).scalar() or 0
                if extra_total <= RANDOM_ORDER_LIMIT:
                    extra_candidates = (
                        extra_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                        .order_by(func.random())
                        .limit(extra_needed)
                        .all()
                    )
                else:
                    extra_ids = sample_movie_ids(extra_query, total=extra_total, limit=extra_needed)
                    extra_raw = (
                        db.query(Movie)
                        .options(selectinload(Movie.genres), selectinload(Movie.moods))
                        .filter(Movie.id.in_(extra_ids))
                        .all()
                    )
                    extra_candidates = reorder_movies_by_id_sequence(extra_raw, extra_ids)
                for candidate in extra_candidates:
                    if _append_candidate(candidate):
                        break

            if len(filler_movies) < filler_needed:
                needed = filler_needed - len(filler_movies)
                pool = featured_movies or base_featured
                filler_movies.extend(pool[:needed])

            featured_movies.extend(filler_movies)

        if len(featured_movies) < featured_rows * featured_row_size:
            shortfall = featured_rows * featured_row_size - len(featured_movies)
            pool = base_featured or featured_movies
            featured_movies.extend(pool[:shortfall])

        if featured_movies:
            attach_poster_themes(featured_movies)
            attach_genre_display(featured_movies)
            if params.order_by == "flic" and flic_filters_payload:
                _assign_flic_scores(featured_movies, flic_filters_payload)

    combined_collections: list[list[Movie]] = []
    if movies:
        combined_collections.append(movies)
    if featured_movies:
        combined_collections.append(featured_movies)

    if combined_collections:
        movie_ids = {
            movie.id
            for collection in combined_collections
            for movie in collection
            if movie.id is not None
        }
        if movie_ids:
            flagged_ids = {
                row[0]
                for row in db.query(MovieFlag.movie_id)
                .filter(MovieFlag.movie_id.in_(movie_ids))
                .all()
            }
            preferences = get_preferences_for_movies(db, active_profile_id, movie_ids)
            for collection in combined_collections:
                for movie in collection:
                    setattr(movie, "flagged", movie.id in flagged_ids)
                    pref = preferences.get(movie.id or 0, {})
                    setattr(movie, "liked", pref.get("liked", False))
                    setattr(movie, "watchlist", pref.get("watchlist", False))

    table_movies = movies

    daily_spotlight_movies = get_daily_spotlight_movies(db, limit=4)

    runtime_cap = (
        params.runtime_max if params.runtime_max is not None else DEFAULT_DOUBLE_FEATURE_RUNTIME
    )
    genre_filter = params.genres[0] if params.genres else None
    mood_filter = params.moods[0] if params.moods else None
    double_feature = pick_double_feature(
        db,
        runtime_cap=runtime_cap,
        genre=genre_filter,
        mood=mood_filter,
        year_min=params.year_min,
        year_max=params.year_max,
    )

    genres_value = ", ".join(params.genres)
    runtime_max_value = params.runtime_max if params.runtime_max is not None else ""
    moods_value = ", ".join(params.moods)
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
        "daily_spotlight_movies": daily_spotlight_movies,
        "double_feature": double_feature,
        "mood_options": mood_options,
        "moods": moods_value,
        "flic_filters_summary": flic_filters_summary,
        "flic_filters_default": flic_filters_default,
        "flic_rank_offset": flic_rank_offset,
        "semantic_active": semantic_active,
        "semantic_enabled": semantic_search_enabled(db),
        "show_ai_search": False,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }

    response = TEMPLATES.TemplateResponse(request, "movies_grid.html", context)
    ensure_profile_cookie(request, response, db)
    cookie_payload = params.to_cookie_payload(page=current_page)
    cookie_payload["semantic"] = 1 if semantic_active else 0
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
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    context = {
        "collection_health": collection_health,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }
    response = TEMPLATES.TemplateResponse(request, "movies_health.html", context)
    ensure_profile_cookie(request, response, db)
    return response


@router.get("/ui/movies/health/missing", response_class=HTMLResponse)
def movies_health_missing(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    base_query = db.query(Movie).order_by(Movie.title.asc())
    missing_runtime = base_query.filter(Movie.runtime.is_(None)).limit(limit).all()
    missing_plot = base_query.filter(or_(Movie.plot.is_(None), Movie.plot == "")).limit(limit).all()
    missing_poster = (
        base_query.filter(or_(Movie.poster_url.is_(None), Movie.poster_url == ""))
        .limit(limit)
        .all()
    )

    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    context = {
        "missing_runtime": missing_runtime,
        "missing_plot": missing_plot,
        "missing_poster": missing_poster,
        "limit": limit,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }
    response = TEMPLATES.TemplateResponse(
        request,
        "movies_health_missing.html",
        context,
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.get("/ui/watchlist", response_class=HTMLResponse)
def watchlist(request: Request, db: Session = Depends(get_db)):
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    movies = get_watchlist_movies(db, profile_id=active_profile_id)
    if movies:
        attach_poster_themes(movies)
        attach_genre_display(movies)
        preferences = get_preferences_for_movies(
            db, active_profile_id, [movie.id for movie in movies if movie.id is not None]
        )
        for movie in movies:
            pref = preferences.get(movie.id or 0, {})
            setattr(movie, "liked", pref.get("liked", False))
            setattr(movie, "watchlist", pref.get("watchlist", False))

    context = {
        "movies": movies,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
        "total": len(movies),
    }
    response = TEMPLATES.TemplateResponse(request, "movies_watchlist.html", context)
    ensure_profile_cookie(request, response, db)
    return response
