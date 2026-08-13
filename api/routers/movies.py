import logging
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.deps.auth import (
    require_admin,
    require_admin_or_profile_admin,
    require_profile_role,
    require_same_origin_provider_work,
    require_same_origin,
)
from api.models.flic_memory import FlicMemory
from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.models.movie_flag import MovieFlag
from api.models.person import Person, Role
from api.schemas.movie import (
    MovieCreate,
    MovieDoubleFeature,
    MovieFlagCreate,
    MovieFlagRead,
    MovieLookupResponse,
    MovieRead,
    MovieSearchResponse,
    MovieUpdate,
    RoleAttach,
    RoleRead,
)
from api.schemas.llm_filters import LlmMovieSearchRequest, LlmMovieSearchResponse
from api.schemas.movie_detail import MovieDetail
from api.schemas.movie_trailer import MovieTrailerRead
from api.services.movies_detail import get_movie_detail
from api.services.movie_trailers import (
    MovieTrailerNotFound,
    get_cached_movie_trailer,
)
from core.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from core.movie_metadata import MovieMetadata
from core.vault_ids import allocate_vault_id, retire_movie_vault_id
from api.utils.pagination import paginate
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupNotFound,
    MovieLookupUnavailable,
    lookup_local_candidates,
    lookup_movie_candidates,
)
from api.services.llm_filters import (
    LlmFilterError,
    LlmProviderUnavailable,
    generate_llm_filters,
)
from api.services.movie_updates import apply_movie_update
from api.services.movie_flags import clear_movie_flag, report_movie_flag, set_movie_flag
from api.services.double_feature import DEFAULT_DOUBLE_FEATURE_RUNTIME, pick_double_feature
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from api.services.profiles import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    get_active_profile_id,
    update_movie_preference,
)
from api.services.trusted_movies import trusted_movie_query
from core.picker import (
    PickerCandidate,
    PickerFilters,
    pick_movie,
)
from api.utils.query_params import parse_optional_non_negative_int


def _build_facets(db: Session, filtered_query) -> dict:
    movie_ids_subquery = filtered_query.with_entities(Movie.id.label("movie_id")).subquery()

    genre_counts = dict(
        db.query(Genre.name, func.count())
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(movie_ids_subquery, movie_ids_subquery.c.movie_id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .all()
    )

    mood_counts = dict(
        db.query(Mood.name, func.count())
        .join(movie_moods, Mood.id == movie_moods.c.mood_id)
        .join(movie_ids_subquery, movie_ids_subquery.c.movie_id == movie_moods.c.movie_id)
        .group_by(Mood.name)
        .all()
    )

    return {"genres": genre_counts, "moods": mood_counts}


router = APIRouter(prefix="/movies", tags=["movies"])
logger = logging.getLogger("vault966")


def _attach_flag_status(db: Session, movies: Sequence[Movie]) -> None:
    if not movies:
        return
    ids = [movie.id for movie in movies if movie.id is not None]
    if not ids:
        return
    flagged_ids = {
        row[0] for row in db.query(MovieFlag.movie_id).filter(MovieFlag.movie_id.in_(ids)).all()
    }
    for movie in movies:
        setattr(movie, "flagged", movie.id in flagged_ids)


def _ensure_movie_exists(db: Session, movie_id: int) -> None:
    exists = db.query(Movie.id).filter(Movie.id == movie_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Movie not found")


def _preference_response(pref) -> dict:
    return {
        "liked": bool(pref.liked) if pref else False,
        "watchlist": bool(pref.watchlist) if pref else False,
    }


def _record_pick_memory(db: Session, movie_id: int) -> None:
    memory_entry = FlicMemory(movie_id=movie_id)
    db.add(memory_entry)
    db.flush()

    # keep last 10 entries
    ids_to_remove = (
        db.query(FlicMemory.id)
        .order_by(FlicMemory.created_at.desc(), FlicMemory.id.desc())
        .offset(10)
        .all()
    )
    if ids_to_remove:
        db.query(FlicMemory).filter(FlicMemory.id.in_([row[0] for row in ids_to_remove])).delete(
            synchronize_session=False
        )


@router.get("/picks", response_model=MovieRead)
def get_pick(
    q: Optional[str] = Query(default=None, description="Case-insensitive search filter"),
    mood: Optional[str] = Query(default=None, description="Desired mood name"),
    genre: Optional[str] = Query(default=None, description="Restrict to this genre"),
    moods: Optional[str] = Query(default=None, description="Comma separated list of mood names"),
    genres: Optional[str] = Query(default=None, description="Comma separated list of genre names"),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_min: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    genre_values = ",".join(value for value in (genres, genre) if value)
    mood_values = ",".join(value for value in (moods, mood) if value)
    params = parse_movie_filters(
        q=q,
        year_min=year_min,
        year_max=year_max,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        genres=genre_values or None,
        moods=mood_values or None,
        order_by="title_asc",
    )

    query = (
        trusted_movie_query(db)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .order_by(Movie.title.asc())
    )
    query = apply_filters(query, params)

    movies = query.all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found for the given filters")

    filters = PickerFilters.from_params(params).to_payload()

    candidates = []
    for movie in movies:
        candidate_payload = PickerCandidate.from_iterables(
            genres=[g.name for g in movie.genres],
            moods=[m.name for m in movie.moods],
            runtime=movie.runtime,
            year=movie.year,
        ).to_payload()
        candidate_payload["id"] = movie.id
        candidate_payload["movie"] = movie
        candidates.append(candidate_payload)

    selection = pick_movie(candidates, filters=filters)
    if selection is None:
        raise HTTPException(status_code=404, detail="No movies available")

    selected_movie = selection.get("movie")
    if selected_movie is None:
        selected_movie = next((movie for movie in movies if movie.id == selection.get("id")), None)
    if selected_movie is None:
        raise HTTPException(status_code=404, detail="No movies available")

    setattr(selected_movie, "flagged", selected_movie.flag is not None)
    return selected_movie


@router.post("/picks/{movie_id}/memory", status_code=204)
def record_pick_memory(
    movie_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> Response:
    _ensure_movie_exists(db, movie_id)
    _record_pick_memory(db, movie_id)
    db.commit()
    return Response(status_code=204)


@router.get("/double-feature", response_model=MovieDoubleFeature)
def get_double_feature(
    genre: Optional[str] = Query(default=None, description="Restrict to this genre"),
    mood: Optional[str] = Query(default=None, description="Desired mood name"),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(
        default=str(DEFAULT_DOUBLE_FEATURE_RUNTIME),
        description="Combined runtime cap (minutes)",
    ),
    db: Session = Depends(get_db),
):
    """Public endpoint for a complementary double-feature pairing."""

    year_min = parse_optional_non_negative_int(year_min, "year_min")
    year_max = parse_optional_non_negative_int(year_max, "year_max")
    runtime_max = parse_optional_non_negative_int(runtime_max, "runtime_max")
    runtime_cap = runtime_max if runtime_max is not None else DEFAULT_DOUBLE_FEATURE_RUNTIME

    selection = pick_double_feature(
        db,
        runtime_cap=runtime_cap,
        genre=genre,
        mood=mood,
        year_min=year_min,
        year_max=year_max,
    )
    if selection is None:
        raise HTTPException(status_code=404, detail="No double feature available")

    _attach_flag_status(db, [selection.primary, selection.secondary])

    return MovieDoubleFeature(
        primary=selection.primary,
        secondary=selection.secondary,
        runtime_cap=selection.runtime_cap,
        total_runtime=selection.total_runtime,
    )


@router.get("/{movie_id}/detail", response_model=MovieDetail)
def movie_detail(movie_id: int, db: Session = Depends(get_db)):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return detail


@router.post("/{movie_id}/detail", response_model=MovieDetail)
def movie_detail_with_provider_similar(
    movie_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin_provider_work("movie_detail_provider")),
):
    detail = get_movie_detail(db, movie_id, include_provider_similar=True)
    if detail is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return detail


@router.get("/{movie_id}/trailer", response_model=MovieTrailerRead)
def movie_trailer(movie_id: int, db: Session = Depends(get_db)):
    try:
        trailer = get_cached_movie_trailer(db, movie_id)
    except MovieTrailerNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MovieTrailerRead(
        site=trailer.site,
        key=trailer.key,
        name=trailer.name,
        url=trailer.url,
        embed_url=trailer.embed_url,
    )


@router.get("/{movie_id}/lookup", response_model=MovieLookupResponse)
def movie_lookup(
    movie_id: int,
    title: Optional[str] = Query(default=None, description="Override title to search"),
    year: Optional[int] = Query(default=None, ge=1870, le=2100),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    movie: Optional[Movie] = db.query(Movie).filter(Movie.id == movie_id).one_or_none()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    search_title = (title or movie.title or "").strip()
    if not search_title:
        raise HTTPException(status_code=400, detail="Movie title is required for lookup")

    search_year = year if year is not None else movie.year

    fallback = lookup_local_candidates(
        db,
        search_title,
        search_year,
        limit=limit,
        exclude_id=movie.id,
    )
    notice = (
        "External lookup requires a same-origin POST—showing vault matches only."
        if fallback
        else "External lookup requires a same-origin POST—no vault matches found."
    )
    return MovieLookupResponse(items=fallback, notice=notice)


@router.post("/{movie_id}/lookup", response_model=MovieLookupResponse)
def movie_lookup_provider(
    movie_id: int,
    title: Optional[str] = Query(default=None, description="Override title to search"),
    year: Optional[int] = Query(default=None, ge=1870, le=2100),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin_provider_work("movie_lookup_provider")),
):
    movie: Optional[Movie] = db.query(Movie).filter(Movie.id == movie_id).one_or_none()
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    search_title = (title or movie.title or "").strip()
    if not search_title:
        raise HTTPException(status_code=400, detail="Movie title is required for lookup")

    search_year = year if year is not None else movie.year

    try:
        candidates = lookup_movie_candidates(search_title, search_year, limit=limit)
        return MovieLookupResponse(items=candidates)
    except MovieLookupUnavailable:
        fallback = lookup_local_candidates(
            db,
            search_title,
            search_year,
            limit=limit,
            exclude_id=movie.id,
        )
        notice = (
            "External lookup unavailable—showing vault matches only."
            if fallback
            else "External lookup unavailable—no vault matches found."
        )
        return MovieLookupResponse(items=fallback, notice=notice)
    except MovieLookupNotFound as exc:
        fallback = lookup_local_candidates(
            db,
            search_title,
            search_year,
            limit=limit,
            exclude_id=movie.id,
        )
        if fallback:
            notice = "No external matches found—showing vault matches."
            return MovieLookupResponse(items=fallback, notice=notice)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MovieLookupError:
        fallback = lookup_local_candidates(
            db,
            search_title,
            search_year,
            limit=limit,
            exclude_id=movie.id,
        )
        notice = (
            "External lookup failed—showing vault matches only."
            if fallback
            else "External lookup failed—no vault matches found."
        )
        return MovieLookupResponse(items=fallback, notice=notice)


@router.get("/search", response_model=MovieSearchResponse)
def search_movies(
    q: Optional[str] = Query(default=None, description="Case-insensitive search on movie title"),
    year_min: Optional[str] = Query(default=None, description="Earliest release year to include"),
    year_max: Optional[str] = Query(default=None, description="Latest release year to include"),
    runtime_min: Optional[str] = Query(default=None, description="Minimum runtime in minutes"),
    runtime_max: Optional[str] = Query(default=None, description="Maximum runtime in minutes"),
    genres: Optional[str] = Query(default=None, description="Comma separated list of genre names"),
    moods: Optional[str] = Query(default=None, description="Comma separated list of mood names"),
    order_by: Optional[str] = Query(default="title_asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    params: MovieFilterParams = parse_movie_filters(
        q=q,
        year_min=year_min,
        year_max=year_max,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        genres=genres,
        moods=moods,
        order_by=order_by,
    )

    base_query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    filtered_query = apply_filters(base_query, params)

    if params.order_by == "flic":
        filters = PickerFilters.from_params(params).to_payload()
        ranked = rank_movie_ids_by_flic(db, base_query=filtered_query, filters=filters)
        total = len(ranked)
        start = (page - 1) * page_size
        end = start + page_size
        page_ids = [movie_id for _, movie_id in ranked[start:end]]
        items = fetch_movies_in_rank_order(
            db,
            ranked_ids=page_ids,
            options=[selectinload(Movie.genres), selectinload(Movie.moods)],
        )
        _attach_flag_status(db, items)
    else:
        clause = ordering_clause(params.order_by)
        ordered_query = filtered_query.order_by(*clause)
        items, total = paginate(ordered_query, page=page, page_size=page_size)
        _attach_flag_status(db, items)

    facets = _build_facets(db, filtered_query)

    return MovieSearchResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        facets=facets,
    )


@router.post("/search/llm", response_model=LlmMovieSearchResponse)
def llm_search_movies(
    payload: LlmMovieSearchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin_provider_work("llm_movie_search")),
):
    allowed_genres = [
        row[0] for row in db.query(Genre.name).order_by(Genre.name.asc()).all() if row[0]
    ]
    allowed_moods = [
        row[0] for row in db.query(Mood.name).order_by(Mood.name.asc()).all() if row[0]
    ]
    try:
        llm_filters = generate_llm_filters(
            payload.query,
            allowed_genres=allowed_genres,
            allowed_moods=allowed_moods,
        )
    except LlmProviderUnavailable as exc:
        logger.warning("llm_movie_search_provider_unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Smart search is temporarily unavailable.",
        ) from exc
    except LlmFilterError as exc:
        logger.warning("llm_movie_search_provider_failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Smart search could not be completed. Please try again.",
        ) from exc

    params: MovieFilterParams = parse_movie_filters(
        q=llm_filters.q,
        year_min=llm_filters.year_min,
        year_max=llm_filters.year_max,
        runtime_min=llm_filters.runtime_min,
        runtime_max=llm_filters.runtime_max,
        genres=llm_filters.genres,
        moods=llm_filters.moods,
        order_by=llm_filters.order_by,
    )

    base_query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    filtered_query = apply_filters(base_query, params)

    page = payload.page
    page_size = payload.page_size

    if params.order_by == "flic":
        filters = PickerFilters.from_params(params).to_payload()
        ranked = rank_movie_ids_by_flic(db, base_query=filtered_query, filters=filters)
        total = len(ranked)
        start = (page - 1) * page_size
        end = start + page_size
        page_ids = [movie_id for _, movie_id in ranked[start:end]]
        items = fetch_movies_in_rank_order(
            db,
            ranked_ids=page_ids,
            options=[selectinload(Movie.genres), selectinload(Movie.moods)],
        )
        _attach_flag_status(db, items)
    else:
        clause = ordering_clause(params.order_by)
        ordered_query = filtered_query.order_by(*clause)
        items, total = paginate(ordered_query, page=page, page_size=page_size)
        _attach_flag_status(db, items)

    facets = _build_facets(db, filtered_query)

    return LlmMovieSearchResponse(
        filters=llm_filters,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        facets=facets,
    )


@router.get("/flags", response_model=List[MovieFlagRead])
def list_flags(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> List[MovieFlagRead]:
    flags = (
        db.query(MovieFlag)
        .order_by(MovieFlag.updated_at.desc(), MovieFlag.movie_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return flags


@router.post("/{movie_id}/flag/report", response_model=MovieFlagRead)
def report_flag(
    movie_id: int,
    payload: MovieFlagCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    flag = report_movie_flag(
        db,
        movie,
        reason=payload.reason,
        notes=payload.notes or None,
        reported_by_profile_id=get_active_profile_id(request, db),
    )
    db.commit()
    db.refresh(flag)
    return flag


@router.patch("/{movie_id}", response_model=MovieRead)
def update_movie(
    movie_id: int,
    payload: MovieUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_profile_admin),
):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    try:
        apply_movie_update(db, movie, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(movie)
    db.commit()
    db.refresh(movie)
    _attach_flag_status(db, [movie])
    return movie


@router.delete("/{movie_id}", status_code=204)
def delete_movie(
    movie_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_profile_admin),
) -> Response:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    retire_movie_vault_id(
        db,
        movie,
        source="movie_delete",
        reason="Movie row deleted through API.",
    )
    db.delete(movie)
    db.commit()
    return Response(status_code=204)


@router.post("/{movie_id}/flag", response_model=MovieFlagRead)
def flag_movie(
    movie_id: int,
    payload: MovieFlagCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
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


@router.delete("/{movie_id}/flag", status_code=204)
def clear_flag(
    movie_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Response:
    clear_movie_flag(db, movie_id)
    db.commit()
    return Response(status_code=204)


@router.post("/{movie_id}/like")
def like_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> dict:
    _ensure_movie_exists(db, movie_id)
    profile_id = get_active_profile_id(request, db)
    pref = update_movie_preference(
        db,
        profile_id=profile_id,
        movie_id=movie_id,
        liked=True,
    )
    return _preference_response(pref)


@router.delete("/{movie_id}/like")
def unlike_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> dict:
    _ensure_movie_exists(db, movie_id)
    profile_id = get_active_profile_id(request, db)
    pref = update_movie_preference(
        db,
        profile_id=profile_id,
        movie_id=movie_id,
        liked=False,
    )
    return _preference_response(pref)


@router.post("/{movie_id}/watchlist")
def watchlist_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> dict:
    _ensure_movie_exists(db, movie_id)
    profile_id = get_active_profile_id(request, db)
    pref = update_movie_preference(
        db,
        profile_id=profile_id,
        movie_id=movie_id,
        watchlist=True,
    )
    return _preference_response(pref)


@router.delete("/{movie_id}/watchlist")
def unwatchlist_movie(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> dict:
    _ensure_movie_exists(db, movie_id)
    profile_id = get_active_profile_id(request, db)
    pref = update_movie_preference(
        db,
        profile_id=profile_id,
        movie_id=movie_id,
        watchlist=False,
    )
    return _preference_response(pref)


@router.get("/", response_model=List[MovieRead])
def list_movies(db: Session = Depends(get_db)):
    movies = db.query(Movie).order_by(Movie.title).limit(200).all()
    _attach_flag_status(db, movies)
    return movies


@router.post("/", response_model=MovieRead)
def create_movie(
    payload: MovieCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    # Upsert genres/moods by name
    genres = []
    for name in payload.genres:
        g = db.query(Genre).filter(Genre.name == name).one_or_none()
        if not g:
            g = Genre(name=name)
            db.add(g)
        genres.append(g)

    moods = []
    for name in payload.moods:
        m = db.query(Mood).filter(Mood.name == name).one_or_none()
        if not m:
            m = Mood(name=name)
            db.add(m)
        moods.append(m)

    metadata = MovieMetadata.from_mapping(payload.model_dump())
    try:
        vault_id = allocate_vault_id(db, metadata.vault_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    movie = Movie(
        vault_id=vault_id,
        title=metadata.title,
        year=metadata.year,
        runtime=metadata.runtime,
        plot=metadata.plot,
        awards=metadata.awards,
        certificate=metadata.certificate,
        keywords=metadata.keywords or None,
        imdb_id=metadata.imdb_id,
        tmdb_id=metadata.tmdb_id,
        imdb_rating=metadata.imdb_rating,
        imdb_votes=metadata.imdb_votes,
        metascore=metadata.metascore,
        tomato_meter=metadata.tomato_meter,
        tomato_audience=metadata.tomato_audience,
        rt_score=metadata.rt_score,
        poster_url=metadata.poster_url,
        backdrop_url=metadata.backdrop_url,
        where_to_watch=metadata.where_to_watch or None,
        languages=metadata.languages or None,
        countries=metadata.countries or None,
        collection=metadata.collection,
        genres=genres,
        moods=moods,
    )
    db.add(movie)
    db.commit()
    db.refresh(movie)
    return movie


@router.post("/{movie_id}/roles", response_model=RoleRead, status_code=201)
def attach_role(
    movie_id: int,
    payload: RoleAttach,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    person = db.get(Person, payload.person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")

    role = Role(
        movie_id=movie_id,
        person_id=payload.person_id,
        role_type=payload.role_type,
        character_name=payload.character_name,
        billing_order=payload.billing_order,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get("/{movie_id}/roles", response_model=List[RoleRead])
def list_roles(movie_id: int, db: Session = Depends(get_db)):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    roles = (
        db.query(Role)
        .options(selectinload(Role.person))
        .filter(Role.movie_id == movie_id)
        .order_by(Role.billing_order.asc(), Role.id.asc())
        .all()
    )
    return roles
