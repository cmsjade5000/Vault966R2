from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.trusted_movies import invalidate_untrusted_movie_cache


def set_movie_flag(
    db: Session,
    movie: Movie,
    *,
    reason: str,
    notes: str | None,
) -> MovieFlag:
    flag = db.get(MovieFlag, movie.id)
    if flag is None:
        flag = MovieFlag(movie_id=movie.id)
        db.add(flag)

    flag.reason = reason
    flag.notes = notes
    flag.updated_at = datetime.now(timezone.utc)
    invalidate_untrusted_movie_cache(db)
    return flag


def clear_movie_flag(db: Session, movie_id: int) -> bool:
    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        return False
    db.delete(flag)
    invalidate_untrusted_movie_cache(db)
    return True


__all__ = ["clear_movie_flag", "set_movie_flag"]
