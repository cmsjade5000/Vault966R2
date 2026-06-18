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
    reported_by_profile_id: int | None = None,
) -> MovieFlag:
    flag = db.get(MovieFlag, movie.id)
    if flag is None:
        flag = MovieFlag(movie_id=movie.id, reported_by_profile_id=reported_by_profile_id)
        db.add(flag)
    elif reported_by_profile_id is not None and flag.reported_by_profile_id is None:
        flag.reported_by_profile_id = reported_by_profile_id

    flag.reason = reason
    flag.notes = notes
    flag.updated_at = datetime.now(timezone.utc)
    invalidate_untrusted_movie_cache(db)
    return flag


def report_movie_flag(
    db: Session,
    movie: Movie,
    *,
    reason: str,
    notes: str | None,
    reported_by_profile_id: int | None,
) -> MovieFlag:
    flag = db.get(MovieFlag, movie.id)
    if flag is None:
        flag = MovieFlag(
            movie_id=movie.id,
            reason=reason,
            notes=notes,
            reported_by_profile_id=reported_by_profile_id,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(flag)
        invalidate_untrusted_movie_cache(db)
        return flag

    if reported_by_profile_id is not None and flag.reported_by_profile_id is None:
        flag.reported_by_profile_id = reported_by_profile_id
        flag.updated_at = datetime.now(timezone.utc)
    return flag


def clear_movie_flag(db: Session, movie_id: int) -> bool:
    flag = db.get(MovieFlag, movie_id)
    if flag is None:
        return False
    db.delete(flag)
    invalidate_untrusted_movie_cache(db)
    return True


__all__ = ["clear_movie_flag", "report_movie_flag", "set_movie_flag"]
