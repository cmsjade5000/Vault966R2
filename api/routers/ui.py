from __future__ import annotations

import json
import pathlib
import random
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from pydantic import BaseModel, Field, validator

from api.db import get_db
from api.models.flic_preset import FlicPreset
from api.models.movie import Genre, Movie, movie_genres
from api.services.movies_detail import get_movie_detail
from api.services.manual_add import (
    append_movie_to_cleaned_csv,
    append_movie_to_enriched_csv,
)
from api.utils.providers import merge_providers
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupUnavailable,
    lookup_movie,
)
from api.services.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from api.services.movies_curated import get_collection_health
from core.poster_theme import select_poster_theme
from core.picker import calculate_flic_score
from core.genres import split_and_normalize

TEMPLATES = Jinja2Templates(
    directory=str(pathlib.Path(__file__).resolve().parents[2] / "templates")
)

router = APIRouter(tags=["ui"])


class ManualMovieMetadata(BaseModel):
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    overview: Optional[str] = None
    runtime: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_date: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    where_to_watch: List[str] = Field(default_factory=list)
    source: Optional[str] = None


class ManualMovieCreate(BaseModel):
    title: str
    year: Optional[int] = None
    metadata: Optional[ManualMovieMetadata] = None
    vudu: Optional[bool] = False

    @validator("title")
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title is required")
        return cleaned

    @validator("year")
    def _validate_year(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 1888 or value > 2100:
            raise ValueError("Year must be between 1888 and 2100")
        return value


class ManualMoviePreviewResponse(BaseModel):
    title: str
    year: Optional[int] = None
    overview: Optional[str] = None
    runtime: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_date: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    where_to_watch: List[str] = Field(default_factory=list)


FILTER_COOKIE_NAME = "movies:lastFilters"
FILTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _load_filter_cookie(request: Request) -> dict[str, object]:
    raw = request.cookies.get(FILTER_COOKIE_NAME)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _attach_poster_themes(movies):
    for movie in movies:
        try:
            genre_names = [
                getattr(genre, "name", None) or "" for genre in getattr(movie, "genres", [])
            ]
        except TypeError:
            genre_names = []
        poster_theme = select_poster_theme(genre_names)
        setattr(movie, "poster_theme", poster_theme)


def _ensure_genres(session: Session, names: List[str]) -> List[Genre]:
    genres: List[Genre] = []
    for label in split_and_normalize(names):
        lowered = label.lower()
        existing = session.query(Genre).filter(func.lower(Genre.name) == lowered).one_or_none()
        if existing is None:
            existing = Genre(name=label)
            session.add(existing)
        genres.append(existing)
    return genres


def _find_existing_movie(session: Session, title: str, year: Optional[int]) -> Optional[Movie]:
    title_lower = title.lower()
    query = session.query(Movie).filter(func.lower(Movie.title) == title_lower)
    if year is None:
        query = query.filter(Movie.year.is_(None))
    else:
        query = query.filter(Movie.year == year)
    return query.first()


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
    cookie_data = _load_filter_cookie(request)
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

    library_total = db.query(func.count(Movie.id)).scalar() or 0
    library_avg_year_value = db.query(func.avg(Movie.year)).filter(Movie.year.isnot(None)).scalar()
    library_avg_year = (
        int(round(library_avg_year_value)) if library_avg_year_value is not None else None
    )
    library_top_genre = (
        db.query(Genre.name, func.count().label("count"))
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(Movie, Movie.id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .order_by(func.count().desc())
        .first()
    )

    stats = {
        "total": library_total,
        "average_year": library_avg_year,
        "top_genre": library_top_genre[0] if library_top_genre else "—",
    }

    taglines = [
        "Your movie buddy—let’s find a vibe.",
        "Shortlist in two taps.",
        "Prefer surprises? I’ve got you.",
    ]
    initial_tagline = random.choice(taglines)

    built_in_presets = [
        {
            "name": "Fresh Favorites",
            "filters": {
                "year_min": 2018,
                "order_by": "year_desc",
                "runtime_max": 150,
            },
            "description": "Recently released crowd-pleasers",
        },
        {
            "name": "Family Night",
            "filters": {
                "genres": ["Animation", "Family"],
                "runtime_max": 110,
                "order_by": "title_asc",
            },
            "description": "Bright picks under two hours for all ages",
        },
        {
            "name": "Quick Thrills",
            "filters": {
                "genres": ["Action", "Thriller"],
                "runtime_max": 110,
                "order_by": "flic",
            },
            "description": "High-energy action under two hours",
        },
        {
            "name": "Comfort 90s",
            "filters": {
                "genres": ["Comedy", "Romance"],
                "year_min": 1990,
                "year_max": 1999,
                "order_by": "title_asc",
            },
            "description": "Feel-good comedies and rom-coms from the 90s",
        },
        {
            "name": "Sci-Fi Epics",
            "filters": {
                "genres": ["Science Fiction", "Adventure"],
                "runtime_max": 185,
                "order_by": "flic",
            },
            "description": "Big-scale sci-fi adventures with high stakes",
        },
        {
            "name": "Docs & Truth",
            "filters": {
                "genres": ["Documentary"],
                "order_by": "year_desc",
            },
            "description": "Recent documentaries with reflective tones",
        },
        {
            "name": "Indie Darlings",
            "filters": {
                "runtime_max": 115,
                "order_by": "flic",
            },
            "description": "Festival favorites with introspective vibes",
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

    raw_genres = [row[0] for row in db.query(Genre.name).order_by(Genre.name.asc()).all() if row[0]]
    genre_options = [
        label
        for label in sorted(split_and_normalize(raw_genres), key=str.casefold)
        if label.lower() not in {"tv movie", "nan"}
    ]

    year_values = [
        row[0]
        for row in db.query(func.distinct(Movie.year)).filter(Movie.year.isnot(None)).all()
        if row[0]
    ]
    decade_options = []
    if year_values:
        min_decade = (min(year_values) // 10) * 10
        max_decade = (max(year_values) // 10) * 10
        for decade in range(min_decade, max_decade + 1, 10):
            decade_options.append(
                {
                    "label": f"{decade}s",
                    "start": decade,
                    "end": decade + 9,
                }
            )

    runtime_presets = [
        {"label": "Any", "value": None},
        {"label": "≤ 90 min", "value": 90},
        {"label": "≤ 120 min", "value": 120},
        {"label": "≤ 150 min", "value": 150},
        {"label": "≤ 180 min", "value": 180},
    ]

    page_size = 30
    if total == 0:
        total_pages = 0
        current_page = 1
        offset = 0
        movies: List[Movie] = []
    else:
        total_pages = (total + page_size - 1) // page_size
        current_page = min(max(current_page, 1), total_pages)
        offset = (current_page - 1) * page_size
        if params.order_by == "flic":
            all_movies = filtered_query.options(
                selectinload(Movie.genres), selectinload(Movie.moods)
            ).all()
            _attach_poster_themes(all_movies)
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
            _attach_poster_themes(movies)
        else:
            clause = ordering_clause(params.order_by)
            movies = (
                filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
                .order_by(clause)
                .offset(offset)
                .limit(page_size)
                .all()
            )
            _attach_poster_themes(movies)

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
    _attach_poster_themes(poster_carousel_movies)

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
        "user_presets": serialized_presets,
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
    }

    response = TEMPLATES.TemplateResponse("movies_grid.html", context)
    cookie_payload = params.to_cookie_payload(page=current_page)
    response.set_cookie(
        FILTER_COOKIE_NAME,
        json.dumps(cookie_payload, separators=(",", ":")),
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


@router.post(
    "/ui/movies/manual-add/preview",
    response_model=ManualMoviePreviewResponse,
)
def manual_add_preview(
    payload: ManualMovieCreate = Body(...),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    year = payload.year

    if _find_existing_movie(db, title, year) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with that title and year already exists.",
        )

    try:
        metadata = lookup_movie(title, year)
    except MovieLookupUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except MovieLookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ManualMoviePreviewResponse(**metadata)


@router.post("/ui/movies/manual-add", status_code=status.HTTP_201_CREATED)
def manual_add_movie(
    payload: ManualMovieCreate = Body(...),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    year = payload.year

    if _find_existing_movie(db, title, year) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with that title and year already exists.",
        )

    metadata_dict = payload.metadata.dict() if payload.metadata is not None else None

    if metadata_dict is None:
        try:
            metadata_dict = lookup_movie(title, year)
        except MovieLookupUnavailable:
            metadata_dict = {}
        except MovieLookupError:
            metadata_dict = {}

    metadata = metadata_dict or {}

    runtime = metadata.get("runtime")
    overview = metadata.get("overview")
    imdb_id = metadata.get("imdb_id")
    tmdb_id = metadata.get("tmdb_id")
    poster_url = metadata.get("poster_url")
    backdrop_url = metadata.get("backdrop_url")

    if imdb_id:
        existing_imdb = db.query(Movie).filter(Movie.imdb_id == imdb_id).first()
        if existing_imdb is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A movie with that IMDb ID already exists.",
            )

    if tmdb_id:
        existing_tmdb = db.query(Movie).filter(Movie.tmdb_id == tmdb_id).first()
        if existing_tmdb is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A movie with that TMDb ID already exists.",
            )

    where_to_watch_list = merge_providers(
        metadata.get("where_to_watch"),
        ["Vudu"] if payload.vudu else [],
    )
    where_to_watch_value = "; ".join(where_to_watch_list) if where_to_watch_list else None

    movie = Movie(
        title=title,
        year=year,
        runtime=runtime,
        plot=overview,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        poster_url=poster_url,
        backdrop_url=backdrop_url,
        where_to_watch=where_to_watch_value,
    )

    genre_objs: List[Genre] = []
    if metadata:
        genre_objs = _ensure_genres(db, metadata.get("genres", []))
        if genre_objs:
            movie.genres = genre_objs

    db.add(movie)
    db.commit()
    db.refresh(movie)

    cleaned_written = append_movie_to_cleaned_csv(title, year)
    enriched_written = append_movie_to_enriched_csv(title, year, metadata, where_to_watch_list)

    return {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "runtime": movie.runtime,
        "overview": movie.plot,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "poster_url": movie.poster_url,
        "backdrop_url": movie.backdrop_url,
        "genres": [genre.name for genre in genre_objs] if genre_objs else [],
        "where_to_watch": where_to_watch_list,
        "csv_updates": {
            "cleaned": cleaned_written,
            "enriched": enriched_written,
        },
        "metadata": metadata,
    }


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
