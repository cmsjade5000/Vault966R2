from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_admin
from api.models.movie import Genre, Movie, MovieIngestProvenance
from api.services.manual_add import (
    append_movie_to_cleaned_csv,
    append_movie_to_enriched_csv,
)
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupUnavailable,
    lookup_movie,
)
from api.utils.providers import merge_providers
from core.genres import split_and_normalize
from core.movie_metadata import MovieMetadata
from core.vault_ids import next_vault_id

router = APIRouter()


class ManualMovieMetadata(BaseModel):
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    overview: Optional[str] = None
    runtime: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_date: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    source: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    where_to_watch: List[str] = Field(default_factory=list)
    awards: Optional[str] = None
    certificate: Optional[str] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    metascore: Optional[int] = None
    tomato_meter: Optional[int] = None
    tomato_audience: Optional[int] = None
    rt_score: Optional[int] = None
    languages: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    collection: Optional[str] = None
    last_tmdb_fetch_at: Optional[str] = None
    last_omdb_fetch_at: Optional[str] = None
    tmdb_payload_sha: Optional[str] = None
    omdb_payload_sha: Optional[str] = None


class ManualMovieCreate(BaseModel):
    title: str
    year: Optional[int] = None
    metadata: Optional[ManualMovieMetadata] = None
    vudu: bool = False

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title is required")
        return cleaned

    @field_validator("year")
    @classmethod
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
    keywords: List[str] = Field(default_factory=list)
    where_to_watch: List[str] = Field(default_factory=list)
    awards: Optional[str] = None
    certificate: Optional[str] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    metascore: Optional[int] = None
    tomato_meter: Optional[int] = None
    tomato_audience: Optional[int] = None
    rt_score: Optional[int] = None
    languages: List[str] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    collection: Optional[str] = None
    last_tmdb_fetch_at: Optional[str] = None
    last_omdb_fetch_at: Optional[str] = None
    tmdb_payload_sha: Optional[str] = None
    omdb_payload_sha: Optional[str] = None


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
    _: None = Depends(require_admin),
):
    title = payload.title.strip()
    year = payload.year

    if _find_existing_movie(db, title, year) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A movie with that title and year already exists.",
        )

    metadata_dict = payload.metadata.model_dump() if payload.metadata is not None else None

    if metadata_dict is None:
        try:
            metadata_dict = lookup_movie(title, year)
        except MovieLookupUnavailable:
            metadata_dict = {}
        except MovieLookupError:
            metadata_dict = {}

    metadata = MovieMetadata.from_mapping(metadata_dict or {})

    runtime = metadata.runtime
    overview = metadata.plot
    imdb_id = metadata.imdb_id
    tmdb_id = metadata.tmdb_id
    poster_url = metadata.poster_url
    backdrop_url = metadata.backdrop_url
    providers = merge_providers(
        metadata.where_to_watch,
        ["Vudu"] if payload.vudu else None,
    )

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

    movie = Movie(
        vault_id=next_vault_id(db),
        title=title,
        year=year,
        runtime=runtime,
        plot=overview,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        imdb_rating=metadata.imdb_rating,
        imdb_votes=metadata.imdb_votes,
        metascore=metadata.metascore,
        tomato_meter=metadata.tomato_meter,
        tomato_audience=metadata.tomato_audience,
        rt_score=metadata.rt_score,
        awards=metadata.awards,
        certificate=metadata.certificate,
        keywords=metadata.keywords or None,
        poster_url=poster_url,
        backdrop_url=backdrop_url,
        where_to_watch=providers or None,
        languages=metadata.languages or None,
        countries=metadata.countries or None,
        collection=metadata.collection,
        last_tmdb_fetch_at=metadata.last_tmdb_fetch_at,
        last_omdb_fetch_at=metadata.last_omdb_fetch_at,
        tmdb_payload_sha=metadata.tmdb_payload_sha,
        omdb_payload_sha=metadata.omdb_payload_sha,
    )

    genre_objs: List[Genre] = []
    if metadata:
        genre_objs = _ensure_genres(db, metadata.genres)
        if genre_objs:
            movie.genres = genre_objs

    db.add(movie)
    db.flush()
    db.add(
        MovieIngestProvenance(
            movie_id=movie.id,
            provider=metadata.source or "manual_add",
            provider_id=metadata.imdb_id
            or (f"tmdb:{metadata.tmdb_id}" if metadata.tmdb_id else None),
            payload_sha=metadata.payload_sha(),
            notes="Created through manual add",
        )
    )
    db.commit()
    db.refresh(movie)

    cleaned_written = append_movie_to_cleaned_csv(title, year)
    enriched_written = append_movie_to_enriched_csv(
        title,
        year,
        metadata.model_dump(mode="json"),
        providers,
    )

    return {
        "id": movie.id,
        "vault_id": movie.vault_id,
        "title": movie.title,
        "year": movie.year,
        "runtime": movie.runtime,
        "overview": movie.plot,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "poster_url": movie.poster_url,
        "backdrop_url": movie.backdrop_url,
        "genres": [genre.name for genre in genre_objs] if genre_objs else [],
        "where_to_watch": providers,
        "csv_updates": {
            "cleaned": cleaned_written,
            "enriched": enriched_written,
        },
        "metadata": metadata.model_dump(mode="json"),
    }
