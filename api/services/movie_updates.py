from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Genre, Movie
from api.schemas.movie import MovieUpdate
from api.utils.providers import merge_providers


def _normalize_genres(db: Session, names: Optional[Sequence[str]]) -> Optional[list[Genre]]:
    if names is None:
        return None
    result: list[Genre] = []
    seen = set()
    for name in names:
        cleaned = (name or "").strip()
        if not cleaned:
            continue
        lower = cleaned.lower()
        if lower in seen:
            continue
        seen.add(lower)
        genre = db.query(Genre).filter(func.lower(Genre.name) == lower).one_or_none()
        if genre is None:
            genre = Genre(name=cleaned)
            db.add(genre)
        result.append(genre)
    return result


def apply_movie_update(db: Session, movie: Movie, payload: MovieUpdate) -> Movie:
    has_changes = False

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise ValueError("Title cannot be blank")
        if title != movie.title:
            movie.title = title
            has_changes = True

    if payload.year is not None and payload.year != movie.year:
        movie.year = payload.year
        has_changes = True

    if payload.runtime is not None and payload.runtime != movie.runtime:
        movie.runtime = payload.runtime
        has_changes = True

    if payload.plot is not None and (payload.plot or None) != movie.plot:
        movie.plot = payload.plot or None
        has_changes = True

    if payload.poster_url is not None and (payload.poster_url or None) != movie.poster_url:
        movie.poster_url = payload.poster_url or None
        has_changes = True

    if payload.backdrop_url is not None and (payload.backdrop_url or None) != movie.backdrop_url:
        movie.backdrop_url = payload.backdrop_url or None
        has_changes = True

    if payload.where_to_watch is not None:
        merged = merge_providers(payload.where_to_watch)
        normalized = "; ".join(merged) if merged else None
        if normalized != movie.where_to_watch:
            movie.where_to_watch = normalized
            has_changes = True

    if payload.genres is not None:
        genre_objs = _normalize_genres(db, payload.genres) or []
        current_names = {genre.name for genre in movie.genres}
        new_names = {genre.name for genre in genre_objs}
        if current_names != new_names:
            movie.genres = genre_objs
            has_changes = True

    if payload.resolve_flag and movie.flag is not None:
        db.delete(movie.flag)
        has_changes = True

    if has_changes and hasattr(movie, "updated_at"):
        movie.updated_at = datetime.now(timezone.utc)

    return movie


__all__ = ["apply_movie_update"]
