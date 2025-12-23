from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import math
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Genre, Movie
from api.schemas.movie import MovieUpdate
from api.utils.providers import merge_providers
from core.enriched_csv import normalize_countries, normalize_languages
from core.genres import split_and_normalize


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


def apply_movie_update(db: Session, movie: Movie, payload: MovieUpdate) -> Movie:
    has_changes = False

    def _set_attr(attr: str, value) -> None:
        nonlocal has_changes
        if getattr(movie, attr) != value:
            setattr(movie, attr, value)
            has_changes = True

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise ValueError("Title cannot be blank")
        _set_attr("title", title)

    if payload.year is not None:
        if payload.year < 1888 or payload.year > 2100:
            raise ValueError("Year must be between 1888 and 2100")
        _set_attr("year", payload.year)

    if payload.runtime is not None:
        if payload.runtime < 0:
            raise ValueError("Runtime cannot be negative")
        _set_attr("runtime", payload.runtime)

    if payload.plot is not None:
        _set_attr("plot", _normalize_optional_text(payload.plot))

    if payload.awards is not None:
        _set_attr("awards", _normalize_optional_text(payload.awards))

    if payload.imdb_id is not None:
        _set_attr("imdb_id", _normalize_optional_text(payload.imdb_id))

    if payload.tmdb_id is not None:
        if payload.tmdb_id < 0:
            raise ValueError("TMDB id cannot be negative")
        _set_attr("tmdb_id", payload.tmdb_id)

    if payload.imdb_rating is not None:
        if math.isnan(payload.imdb_rating) or not (0 <= payload.imdb_rating <= 10):
            raise ValueError("IMDb rating must be between 0 and 10")
        _set_attr("imdb_rating", payload.imdb_rating)

    if payload.imdb_votes is not None:
        if payload.imdb_votes < 0:
            raise ValueError("IMDb votes cannot be negative")
        _set_attr("imdb_votes", payload.imdb_votes)

    if payload.metascore is not None:
        if payload.metascore < 0 or payload.metascore > 100:
            raise ValueError("Metascore must be between 0 and 100")
        _set_attr("metascore", payload.metascore)

    if payload.tomato_meter is not None:
        if payload.tomato_meter < 0 or payload.tomato_meter > 100:
            raise ValueError("Tomatometer score must be between 0 and 100")
        _set_attr("tomato_meter", payload.tomato_meter)

    if payload.tomato_audience is not None:
        if payload.tomato_audience < 0 or payload.tomato_audience > 100:
            raise ValueError("Audience score must be between 0 and 100")
        _set_attr("tomato_audience", payload.tomato_audience)

    if payload.rt_score is not None:
        if payload.rt_score < 0 or payload.rt_score > 100:
            raise ValueError("Rotten Tomatoes score must be between 0 and 100")
        _set_attr("rt_score", payload.rt_score)

    if payload.poster_url is not None:
        _set_attr("poster_url", _normalize_optional_text(payload.poster_url))

    if payload.backdrop_url is not None:
        _set_attr("backdrop_url", _normalize_optional_text(payload.backdrop_url))

    if payload.where_to_watch is not None:
        merged = merge_providers(payload.where_to_watch)
        normalized = "; ".join(merged) if merged else None
        _set_attr("where_to_watch", normalized)

    if payload.languages is not None:
        raw = payload.languages
        if isinstance(raw, list):
            raw_text = "; ".join(str(item) for item in raw if item is not None)
        else:
            raw_text = str(raw) if raw is not None else ""
        codes = normalize_languages(raw_text).iso
        _set_attr("languages", codes or None)

    if payload.countries is not None:
        raw = payload.countries
        if isinstance(raw, list):
            raw_text = "; ".join(str(item) for item in raw if item is not None)
        else:
            raw_text = str(raw) if raw is not None else ""
        codes = normalize_countries(raw_text).iso
        _set_attr("countries", codes or None)

    if payload.collection is not None:
        _set_attr("collection", _normalize_optional_text(payload.collection))

    if payload.last_tmdb_fetch_at is not None:
        _set_attr("last_tmdb_fetch_at", _normalize_datetime(payload.last_tmdb_fetch_at))

    if payload.last_omdb_fetch_at is not None:
        _set_attr("last_omdb_fetch_at", _normalize_datetime(payload.last_omdb_fetch_at))

    if payload.tmdb_etag is not None:
        _set_attr("tmdb_etag", _normalize_optional_text(payload.tmdb_etag))

    if payload.tmdb_payload_sha is not None:
        _set_attr("tmdb_payload_sha", _normalize_optional_text(payload.tmdb_payload_sha))

    if payload.omdb_payload_sha is not None:
        _set_attr("omdb_payload_sha", _normalize_optional_text(payload.omdb_payload_sha))

    if payload.genres is not None:
        genre_objs = _normalize_genres(db, payload.genres) or []
        current_names = {genre.name for genre in movie.genres}
        new_names = {genre.name for genre in genre_objs}
        if current_names != new_names:
            movie.genres = genre_objs
            has_changes = True

    if payload.resolve_flag and movie.flag is not None:
        db.delete(movie.flag)

    if has_changes and hasattr(movie, "updated_at"):
        movie.updated_at = datetime.now(timezone.utc)

    return movie


__all__ = ["apply_movie_update"]
