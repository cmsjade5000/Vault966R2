from __future__ import annotations

from typing import Iterable, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.db import get_db
from api.deps.auth import require_profile_role, require_provider_work_budget, require_same_origin
from api.models.movie import Movie
from api.models.source_sync import SourceSnapshot
from api.schemas.movie import MovieFlagCreate, MovieFlagRead
from api.services.movie_flags import clear_movie_flag, report_movie_flag, set_movie_flag
from api.services.movies_curated import get_collection_health
from api.services.source_sync import latest_active_snapshot, snapshot_summary
from api.services.ui.grid import (
    FILTER_COOKIE_MAX_AGE,
    FILTER_COOKIE_NAME,
    FILTER_COOKIE_PATH,
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
from api.services.ui.templates import TEMPLATES
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from api.services.profiles import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    ensure_profile_cookie,
    get_active_profile_role,
    get_active_profile_id,
    get_preferences_for_movies,
    get_profiles,
    get_watchlist_movies,
)
from api.routers.ui.review import build_review_context
from api.services.semantic_search import (
    SemanticSearchError,
    SemanticSearchUnavailable,
    apply_semantic_query_overrides,
    parse_semantic_intent,
    semantic_query_forces_animation,
    semantic_search_enabled,
    semantic_search_movies,
)
from api.services.trusted_movies import get_untrusted_movie_ids
from core.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from core.picker import PickerCandidate, PickerFilters, calculate_flic_score

router = APIRouter()

LIBRARY_PRESETS = {
    "recently-added",
    "under-100",
    "highly-rated",
    "hidden-gems",
    "before-2000",
    "edition-cuts",
}
LIBRARY_PRESET_CHIPS = [
    {
        "key": "recently-added",
        "name": "Recently Added",
        "description": "Newest Vault entries first.",
    },
    {
        "key": "under-100",
        "name": "Under 100",
        "description": "Shorter movie-night picks.",
    },
    {
        "key": "highly-rated",
        "name": "Highly Rated",
        "description": "Strong IMDb or Rotten Tomatoes scores.",
    },
    {
        "key": "hidden-gems",
        "name": "Hidden Gems",
        "description": "Well-liked titles with fewer IMDb votes.",
    },
    {
        "key": "before-2000",
        "name": "Before 2000",
        "description": "Older shelf favorites.",
    },
    {
        "key": "edition-cuts",
        "name": "Edition Cuts",
        "description": "Extended, unrated, and named editions.",
    },
]

LIBRARY_PAGE_SIZE = 36
LIBRARY_FILTER_QUERY_KEYS = {
    "q",
    "genres",
    "moods",
    "year_min",
    "year_max",
    "runtime_min",
    "runtime_max",
    "order_by",
    "preset",
    "semantic",
}


def _apply_library_preset(query, preset: str | None):
    if preset == "under-100":
        return query.filter(Movie.runtime.isnot(None), Movie.runtime <= 100)
    if preset == "highly-rated":
        return query.filter(
            or_(
                (Movie.imdb_rating >= 7.5) & (Movie.imdb_votes >= 10_000),
                Movie.rt_score >= 85,
            )
        )
    if preset == "hidden-gems":
        return query.filter(
            Movie.imdb_rating >= 6.8,
            Movie.imdb_votes.isnot(None),
            Movie.imdb_votes < 100_000,
        )
    if preset == "before-2000":
        return query.filter(Movie.year.isnot(None), Movie.year < 2000)
    if preset == "edition-cuts":
        markers = (
            "%(Unrated)%",
            "%(Extended%",
            "%Director's Cut%",
            "%Special Edition%",
            "%Anniversary Edition%",
            "%Final Cut%",
        )
        return query.filter(or_(*(Movie.title.ilike(marker) for marker in markers)))
    return query


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
    q: Optional[str] = Query(default=None, max_length=120),
    genres: Optional[str] = Query(default=None),
    moods: Optional[str] = Query(default=None),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    order_by: str = Query(default="title_asc"),
    view: str = Query(default="grid", pattern="^(grid|list)$"),
    preset: Optional[str] = Query(default=None, max_length=30),
    semantic: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    cookie_data = load_filter_cookie(request)
    query_params = request.query_params
    using_filter_query = "_filters" in query_params or any(
        key in query_params for key in LIBRARY_FILTER_QUERY_KEYS
    )

    def resolve(source_value, key):
        return source_value if using_filter_query else cookie_data.get(key)

    resolved_view = resolve(view, "view") or "grid"
    if "view" in query_params:
        resolved_view = view
    if resolved_view not in {"grid", "list"}:
        resolved_view = "grid"
    resolved_preset = resolve(preset, "preset")
    if resolved_preset not in LIBRARY_PRESETS:
        resolved_preset = None

    try:
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
    except HTTPException:
        if using_filter_query:
            raise
        params = parse_movie_filters(
            q=None,
            year_min=None,
            year_max=None,
            runtime_min=None,
            runtime_max=None,
            genres=None,
            moods=None,
            order_by="title_asc",
        )
        resolved_preset = None

    semantic_value = resolve(semantic, "semantic")
    semantic_active = str(semantic_value).lower() in {"1", "true", "yes", "on"}
    current_page = page
    if "page" not in query_params and not using_filter_query:
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
    library_total = base_query.with_entities(func.count(Movie.id)).scalar() or 0
    filtered_query = _apply_library_preset(apply_filters(base_query, params), resolved_preset)
    total = filtered_query.with_entities(func.count(Movie.id)).scalar() or 0

    stats = query_library_stats(db)
    active_role = get_active_profile_role(request, db)
    taglines, initial_tagline = get_taglines()
    built_in_presets = get_built_in_presets()
    user_presets = serialize_user_presets(db)
    genre_options = get_genre_options(db)
    mood_options = get_mood_options(db)
    decade_options = get_decade_options(db)
    runtime_presets = get_runtime_presets()

    page_size = LIBRARY_PAGE_SIZE
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
            require_provider_work_budget(request, scope="semantic_search")

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
                effective_order = (
                    "id_desc" if resolved_preset == "recently-added" else params.order_by
                )
                clause = ordering_clause(effective_order)
                movies = (
                    filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                    .order_by(*clause)
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
            effective_order = "id_desc" if resolved_preset == "recently-added" else params.order_by
            clause = ordering_clause(effective_order)
            movies = (
                filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                .order_by(*clause)
                .offset(offset)
                .limit(page_size)
                .all()
            )
            attach_poster_themes(movies)
            attach_genre_display(movies)

    if movies:
        movie_ids = {movie.id for movie in movies if movie.id is not None}
        if movie_ids:
            review_ids = get_untrusted_movie_ids(db, movie_ids)
            preferences = get_preferences_for_movies(db, active_profile_id, movie_ids)
            for movie in movies:
                setattr(movie, "flagged", movie.id in review_ids)
                pref = preferences.get(movie.id or 0, {})
                setattr(movie, "liked", pref.get("liked", False))
                setattr(movie, "watchlist", pref.get("watchlist", False))

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
        "library_total": library_total,
        "is_library_empty": library_total == 0,
        "total_pages": total_pages,
        "page_size": page_size,
        "stats": stats,
        "can_start_first_import": active_role == ROLE_ADMIN,
        "taglines": taglines,
        "initial_tagline": initial_tagline,
        "built_in_presets": built_in_presets,
        "library_presets": LIBRARY_PRESET_CHIPS,
        "user_presets": user_presets,
        "year_min": year_min_value,
        "year_max": year_max_value,
        "runtime_max": runtime_max_value,
        "order_by": params.order_by,
        "genre_options": genre_options,
        "decade_options": decade_options,
        "runtime_presets": runtime_presets,
        "view": resolved_view,
        "preset": resolved_preset,
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
    cookie_payload["view"] = resolved_view
    cookie_payload["preset"] = resolved_preset or ""
    response.set_cookie(
        FILTER_COOKIE_NAME,
        dump_filter_cookie(cookie_payload),
        max_age=FILTER_COOKIE_MAX_AGE,
        samesite="lax",
        path=FILTER_COOKIE_PATH,
    )
    return response


@router.post("/ui/movies/{movie_id}/review-flag")
def flag_movie_for_review(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> dict[str, int | bool]:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    report_movie_flag(
        db,
        movie,
        reason="Human review",
        notes="Flagged for review",
        reported_by_profile_id=get_active_profile_id(request, db),
    )
    db.commit()

    return {"movie_id": movie_id, "flagged": True}


@router.put("/ui/movies/{movie_id}/flag", response_model=MovieFlagRead)
def manage_movie_flag(
    movie_id: int,
    payload: MovieFlagCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> MovieFlagRead:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    flag = set_movie_flag(
        db,
        movie,
        reason=payload.reason,
        notes=payload.notes or None,
    )
    db.commit()
    db.refresh(flag)
    return flag


@router.delete("/ui/movies/{movie_id}/flag", status_code=204)
def resolve_movie_flag(
    movie_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> Response:
    clear_movie_flag(db, movie_id)
    db.commit()
    return Response(status_code=204)


@router.get("/ui/movies/health", response_class=HTMLResponse)
def movies_health(
    request: Request,
    view: str | None = None,
    row: int | None = Query(default=None, ge=1),
    movie: int | None = Query(default=None, ge=1),
    undo_decision: int | None = Query(default=None, ge=1),
    flag_reason: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    collection_health = get_collection_health(db)
    source_snapshots = (
        db.query(SourceSnapshot)
        .order_by(SourceSnapshot.uploaded_at.desc(), SourceSnapshot.id.desc())
        .limit(20)
        .all()
    )
    latest_source_snapshot = latest_active_snapshot(db)
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)
    active_role = get_active_profile_role(request, db)
    context = {
        "collection_health": collection_health,
        "source_snapshots": source_snapshots,
        "latest_source_snapshot": latest_source_snapshot,
        "latest_source_summary": snapshot_summary(db, latest_source_snapshot),
        "profiles": profiles,
        "active_profile_id": active_profile_id,
        "can_manage_health": active_role == ROLE_ADMIN,
        **build_review_context(
            request,
            db,
            view=view,
            row=row,
            movie=movie,
            undo_decision=undo_decision,
            flag_reason=flag_reason,
        ),
    }
    response = TEMPLATES.TemplateResponse(request, "movies_health.html", context)
    ensure_profile_cookie(request, response, db)
    return response


@router.get("/ui/movies/health/missing", response_class=HTMLResponse)
def movies_health_missing(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
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
