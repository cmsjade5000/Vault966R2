from datetime import datetime, timezone
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.deps.auth import require_admin_if_configured
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
from api.services.movies_detail import get_movie_detail
from core.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from api.utils.pagination import paginate
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupNotFound,
    MovieLookupUnavailable,
    lookup_movie_candidates,
)
from api.services.llm_filters import (
    LlmFilterError,
    LlmProviderUnavailable,
    generate_llm_filters,
)
from api.services.movie_updates import apply_movie_update
from api.services.double_feature import DEFAULT_DOUBLE_FEATURE_RUNTIME, pick_double_feature
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from core.picker import (
    PickerCandidate,
    PickerFilters,
    pick_movie,
)
from api.utils.query_params import parse_optional_non_negative_int

router = APIRouter(prefix="/movies", tags=["movies"])


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


@router.get("/picks", response_model=MovieRead)
def get_pick(
    mood: Optional[str] = Query(default=None, description="Desired mood name"),
    genre: Optional[str] = Query(default=None, description="Restrict to this genre"),
    year_min: Optional[str] = Query(default=None),
    year_max: Optional[str] = Query(default=None),
    runtime_max: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    year_min = parse_optional_non_negative_int(year_min, "year_min")
    year_max = parse_optional_non_negative_int(year_max, "year_max")
    runtime_max = parse_optional_non_negative_int(runtime_max, "runtime_max")
    if year_min is not None and year_max is not None and year_min > year_max:
        raise HTTPException(status_code=400, detail="year_min cannot be greater than year_max")

    query = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .order_by(Movie.title.asc())
    )

    if genre:
        query = query.filter(Movie.genres.any(Genre.name == genre))
    if year_min is not None:
        query = query.filter(Movie.year >= year_min)
    if year_max is not None:
        query = query.filter(Movie.year <= year_max)
    if runtime_max is not None:
        query = query.filter(Movie.runtime <= runtime_max)
    if mood:
        query = query.filter(Movie.moods.any(Mood.name == mood))

    movies = query.all()
    if not movies:
        raise HTTPException(status_code=404, detail="No movies found for the given filters")

    filters = PickerFilters.from_values(
        moods=[mood] if mood else (),
        genres=[genre] if genre else (),
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    ).to_payload()

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

    memory_entry = FlicMemory(movie_id=selected_movie.id)
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

    db.commit()

    setattr(selected_movie, "flagged", selected_movie.flag is not None)
    return selected_movie


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

    try:
        candidates = lookup_movie_candidates(search_title, search_year, limit=limit)
    except MovieLookupUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MovieLookupNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MovieLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return MovieLookupResponse(items=candidates)


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
        ordered_query = filtered_query.order_by(clause)
        items, total = paginate(ordered_query, page=page, page_size=page_size)
        _attach_flag_status(db, items)

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

    facets = {
        "genres": genre_counts,
        "moods": mood_counts,
    }

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
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LlmFilterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
        ordered_query = filtered_query.order_by(clause)
        items, total = paginate(ordered_query, page=page, page_size=page_size)
        _attach_flag_status(db, items)

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

    facets = {
        "genres": genre_counts,
        "moods": mood_counts,
    }

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
) -> List[MovieFlagRead]:
    flags = (
        db.query(MovieFlag)
        .order_by(MovieFlag.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return flags


@router.patch("/{movie_id}", response_model=MovieRead)
def update_movie(
    movie_id: int,
    payload: MovieUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_if_configured),
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


@router.post("/{movie_id}/flag", response_model=MovieFlagRead)
def flag_movie(
    movie_id: int,
    payload: MovieFlagCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_if_configured),
):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        flag = MovieFlag(movie_id=movie_id)
        db.add(flag)

    flag.reason = payload.reason
    if payload.notes and len(payload.notes) > 500:
        raise HTTPException(status_code=400, detail="Notes must be 500 characters or less")
    flag.notes = payload.notes
    flag.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(flag)
    return flag


@router.delete("/{movie_id}/flag", status_code=204)
def clear_flag(
    movie_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_if_configured),
) -> Response:
    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        return Response(status_code=204)
    db.delete(flag)
    db.commit()
    return Response(status_code=204)


@router.get("/", response_model=List[MovieRead])
def list_movies(db: Session = Depends(get_db)):
    movies = db.query(Movie).order_by(Movie.title).limit(200).all()
    _attach_flag_status(db, movies)
    return movies


@router.post("/", response_model=MovieRead)
def create_movie(
    payload: MovieCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_if_configured),
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

    movie = Movie(
        title=payload.title,
        year=payload.year,
        runtime=payload.runtime,
        plot=payload.plot,
        imdb_id=payload.imdb_id,
        tmdb_id=payload.tmdb_id,
        poster_url=payload.poster_url,
        backdrop_url=payload.backdrop_url,
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
    _: None = Depends(require_admin_if_configured),
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
