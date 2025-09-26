from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.deps.auth import require_admin
from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.models.movie_flag import MovieFlag
from api.models.person import Person, Role
from api.schemas.movie import (
    MovieCreate,
    MovieFlagCreate,
    MovieFlagRead,
    MovieRead,
    MovieSearchResponse,
    MovieUpdate,
    RoleAttach,
    RoleRead,
)
from api.schemas.movie_detail import MovieDetail
from api.services.movies_detail import get_movie_detail
from api.services.movie_filters import (
    MovieFilterParams,
    parse_movie_filters,
)
from api.services.movie_picks import MovieSelectionError, pick_movie
from api.services.movie_search import attach_flag_status, search_movies as search_movies_service
from api.services.movie_updates import apply_movie_update
from api.utils.query_params import parse_optional_non_negative_int

router = APIRouter(prefix="/movies", tags=["movies"])


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

    try:
        return pick_movie(
            db,
            mood=mood,
            genre=genre,
            year_min=year_min,
            year_max=year_max,
            runtime_max=runtime_max,
        )
    except MovieSelectionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{movie_id}/detail", response_model=MovieDetail)
def movie_detail(movie_id: int, db: Session = Depends(get_db)):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return detail


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

    result = search_movies_service(
        db,
        params,
        page=page,
        page_size=page_size,
        clamp_page=False,
    )
    attach_flag_status(db, result.items)

    return MovieSearchResponse(
        items=result.items,
        total=result.total,
        page=page,
        page_size=page_size,
        facets=result.facets,
    )


@router.get("/flags", response_model=List[MovieFlagRead])
def list_flags(db: Session = Depends(get_db)) -> List[MovieFlagRead]:
    flags = db.query(MovieFlag).order_by(MovieFlag.updated_at.desc()).all()
    return flags


@router.patch("/{movie_id}", response_model=MovieRead)
def update_movie(
    movie_id: int,
    payload: MovieUpdate,
    db: Session = Depends(get_db),
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
    attach_flag_status(db, [movie])
    return movie


@router.post("/{movie_id}/flag", response_model=MovieFlagRead)
def flag_movie(
    movie_id: int,
    payload: MovieFlagCreate,
    db: Session = Depends(get_db),
):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")

    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        flag = MovieFlag(movie_id=movie_id)
        db.add(flag)

    flag.reason = payload.reason
    flag.notes = payload.notes
    flag.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(flag)
    return flag


@router.delete("/{movie_id}/flag", status_code=204)
def clear_flag(movie_id: int, db: Session = Depends(get_db)) -> Response:
    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        return Response(status_code=204)
    db.delete(flag)
    db.commit()
    return Response(status_code=204)


@router.get("/", response_model=List[MovieRead])
def list_movies(db: Session = Depends(get_db)):
    movies = db.query(Movie).order_by(Movie.title).limit(200).all()
    attach_flag_status(db, movies)
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
