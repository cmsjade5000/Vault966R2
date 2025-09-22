from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import Base, engine, get_db
from api.deps.auth import require_admin
from api.models.flic_memory import FlicMemory
from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.models.person import Person, Role
from api.schemas.movie import (
    MovieCreate,
    MovieRead,
    MovieSearchResponse,
    RoleAttach,
    RoleRead,
)
from api.schemas.movie_detail import MovieDetail
from api.services.movies_detail import get_movie_detail
from api.utils.pagination import paginate
from core.picker import calculate_flic_score, pick_movie

# Ensure tables exist on import (simple dev behavior; move to Alembic later)
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/movies", tags=["movies"])


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("/picks", response_model=MovieRead)
def get_pick(
    mood: Optional[str] = Query(default=None, description="Desired mood name"),
    genre: Optional[str] = Query(default=None, description="Restrict to this genre"),
    year_min: Optional[int] = Query(default=None, ge=0),
    year_max: Optional[int] = Query(default=None, ge=0),
    runtime_max: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
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

    filters = {
        "moods": [mood] if mood else [],
        "genres": [genre] if genre else [],
        "year_min": year_min,
        "year_max": year_max,
        "runtime_max": runtime_max,
    }

    candidates = []
    for movie in movies:
        candidates.append(
            {
                "id": movie.id,
                "movie": movie,
                "moods": [m.name for m in movie.moods],
                "genres": [g.name for g in movie.genres],
                "runtime": movie.runtime,
                "year": movie.year,
            }
        )

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

    return selected_movie


@router.get("/{movie_id}/detail", response_model=MovieDetail)
def movie_detail(movie_id: int, db: Session = Depends(get_db)):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return detail


@router.get("/search", response_model=MovieSearchResponse)
def search_movies(
    q: Optional[str] = Query(default=None, description="Case-insensitive search on movie title"),
    year_min: Optional[int] = Query(default=None, ge=0),
    year_max: Optional[int] = Query(default=None, ge=0),
    runtime_min: Optional[int] = Query(default=None, ge=0),
    runtime_max: Optional[int] = Query(default=None, ge=0),
    genres: Optional[str] = Query(default=None, description="Comma separated list of genre names"),
    moods: Optional[str] = Query(default=None, description="Comma separated list of mood names"),
    order_by: str = Query(default="title_asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))

    if q:
        query = query.filter(Movie.title.ilike(f"%{q.strip()}%"))

    if year_min is not None:
        query = query.filter(Movie.year >= year_min)
    if year_max is not None:
        query = query.filter(Movie.year <= year_max)

    if runtime_min is not None:
        query = query.filter(Movie.runtime >= runtime_min)
    if runtime_max is not None:
        query = query.filter(Movie.runtime <= runtime_max)

    genre_filters = _parse_csv(genres)
    for genre_name in genre_filters:
        query = query.filter(Movie.genres.any(Genre.name == genre_name))

    mood_filters = _parse_csv(moods)
    for mood_name in mood_filters:
        query = query.filter(Movie.moods.any(Mood.name == mood_name))

    ordering_map = {
        "title_asc": Movie.title.asc(),
        "title_desc": Movie.title.desc(),
        "year_desc": Movie.year.desc(),
        "runtime_asc": Movie.runtime.asc(),
        "flic": None,
    }

    if order_by not in ordering_map:
        raise HTTPException(status_code=400, detail="Invalid order_by value")

    if order_by == "flic":
        all_movies = query.options(selectinload(Movie.genres), selectinload(Movie.moods)).all()
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
        total = len(scored)
        start = (page - 1) * page_size
        end = start + page_size
        items = [movie for _, movie in scored[start:end]]
    else:
        ordered_query = query.order_by(ordering_map[order_by])
        items, total = paginate(ordered_query, page=page, page_size=page_size)

    movie_ids_subquery = query.with_entities(Movie.id.label("movie_id")).subquery()

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


@router.get("/", response_model=List[MovieRead])
def list_movies(db: Session = Depends(get_db)):
    return db.query(Movie).order_by(Movie.title).limit(200).all()


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
