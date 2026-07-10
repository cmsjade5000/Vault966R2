from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import math
from typing import Callable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Genre, Movie
from api.schemas.movie import MovieUpdate
from api.services.movie_review import apply_title_year_authority
from api.utils.providers import merge_providers
from core.enriched_csv import NormalizedCodes, normalize_countries, normalize_languages
from core.genres import split_and_normalize


_OPTIONAL_TEXT_FIELDS = (
    "plot",
    "awards",
    "certificate",
    "imdb_id",
    "poster_url",
    "backdrop_url",
    "collection",
    "tmdb_etag",
    "tmdb_payload_sha",
    "omdb_payload_sha",
)
_DATETIME_FIELDS = ("last_tmdb_fetch_at", "last_omdb_fetch_at")
_RANGE_RULES = {
    "year": (1888, 2100, "Year must be between 1888 and 2100"),
    "runtime": (0, None, "Runtime cannot be negative"),
    "tmdb_id": (0, None, "TMDB id cannot be negative"),
    "imdb_rating": (0, 10, "IMDb rating must be between 0 and 10"),
    "imdb_votes": (0, None, "IMDb votes cannot be negative"),
    "metascore": (0, 100, "Metascore must be between 0 and 100"),
    "tomato_meter": (0, 100, "Tomatometer score must be between 0 and 100"),
    "tomato_audience": (0, 100, "Audience score must be between 0 and 100"),
    "rt_score": (0, 100, "Rotten Tomatoes score must be between 0 and 100"),
}


def _normalize_genres(db: Session, names: Optional[Sequence[str]]) -> Optional[list[Genre]]:
    if names is None:
        return None
    result: list[Genre] = []
    normalized_names = split_and_normalize(names)
    for name in normalized_names:
        cleaned = name.strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        genre = db.query(Genre).filter(func.lower(Genre.name) == lower).one_or_none()
        if genre is None:
            genre = Genre(name=cleaned)
            db.add(genre)
        result.append(genre)
    return result


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _set_attr(movie: Movie, attr: str, value: object) -> bool:
    if getattr(movie, attr) == value:
        return False
    setattr(movie, attr, value)
    return True


def _normalize_keywords(values: Sequence[str]) -> list[str] | None:
    keywords: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = str(item).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            keywords.append(cleaned)
    return keywords or None


def _normalize_code_values(
    value: str | list[str],
    normalizer: Callable[[str | None], NormalizedCodes],
) -> list[str] | None:
    if isinstance(value, list):
        raw_text = "; ".join(str(item) for item in value if item is not None)
    else:
        raw_text = str(value)
    return normalizer(raw_text).iso or None


def _apply_title(movie: Movie, title_value: str | None) -> bool:
    if title_value is None:
        return False
    title = title_value.strip()
    if not title:
        raise ValueError("Title cannot be blank")
    return _set_attr(movie, "title", title)


def _apply_ranged_fields(movie: Movie, payload: MovieUpdate) -> bool:
    changed = False
    for field_name, (minimum, maximum, message) in _RANGE_RULES.items():
        value = getattr(payload, field_name)
        if value is None:
            continue
        if isinstance(value, float) and math.isnan(value):
            raise ValueError(message)
        if value < minimum or (maximum is not None and value > maximum):
            raise ValueError(message)
        changed |= _set_attr(movie, field_name, value)
    return changed


def _apply_optional_text_fields(movie: Movie, payload: MovieUpdate) -> bool:
    changed = False
    for field_name in _OPTIONAL_TEXT_FIELDS:
        value = getattr(payload, field_name)
        if value is not None:
            changed |= _set_attr(movie, field_name, _normalize_optional_text(value))
    return changed


def _apply_collection_fields(movie: Movie, payload: MovieUpdate) -> bool:
    changed = False
    if payload.keywords is not None:
        changed |= _set_attr(movie, "keywords", _normalize_keywords(payload.keywords))
    if payload.where_to_watch is not None:
        changed |= _set_attr(
            movie, "where_to_watch", merge_providers(payload.where_to_watch) or None
        )
    if payload.languages is not None:
        changed |= _set_attr(
            movie,
            "languages",
            _normalize_code_values(payload.languages, normalize_languages),
        )
    if payload.countries is not None:
        changed |= _set_attr(
            movie,
            "countries",
            _normalize_code_values(payload.countries, normalize_countries),
        )
    return changed


def _apply_datetime_fields(movie: Movie, payload: MovieUpdate) -> bool:
    changed = False
    for field_name in _DATETIME_FIELDS:
        value = getattr(payload, field_name)
        if value is not None:
            changed |= _set_attr(movie, field_name, _normalize_datetime(value))
    return changed


def _apply_genres(db: Session, movie: Movie, names: Optional[Sequence[str]]) -> bool:
    if names is None:
        return False
    genres = _normalize_genres(db, names) or []
    if {genre.name for genre in movie.genres} == {genre.name for genre in genres}:
        return False
    movie.genres = genres
    return True


def apply_movie_update(db: Session, movie: Movie, payload: MovieUpdate) -> Movie:
    changes = (
        _apply_title(movie, payload.title),
        _apply_ranged_fields(movie, payload),
        _apply_optional_text_fields(movie, payload),
        _apply_collection_fields(movie, payload),
        _apply_datetime_fields(movie, payload),
        _apply_genres(db, movie, payload.genres),
    )
    has_changes = any(changes)

    if payload.resolve_flag and movie.flag is not None:
        db.delete(movie.flag)

    if payload.title is not None:
        if apply_title_year_authority(db, movie=movie, profile_id=None):
            has_changes = True

    if has_changes and hasattr(movie, "updated_at"):
        movie.updated_at = datetime.now(timezone.utc)

    return movie


__all__ = ["apply_movie_update"]
