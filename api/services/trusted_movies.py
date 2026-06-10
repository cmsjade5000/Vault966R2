from __future__ import annotations

from sqlalchemy.orm import Query, Session

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.movie_review import get_review_queue
from api.services.source_sync import get_source_review_queue


def get_untrusted_movie_ids(db: Session) -> set[int]:
    """Return movies with any unresolved identity or metadata review work."""
    cached = db.info.get("untrusted_movie_ids")
    if cached is not None:
        return set(cached)

    movie_ids = {
        movie_id for (movie_id,) in db.query(MovieFlag.movie_id).all() if movie_id is not None
    }

    review_queue, _ = get_review_queue(db)
    movie_ids.update(item.movie.id for item in review_queue if item.movie.id is not None)

    for item in get_source_review_queue(db):
        if item.movie is not None and item.movie.id is not None:
            movie_ids.add(item.movie.id)
        movie_ids.update(
            candidate.id for candidate in item.candidate_movies if candidate.id is not None
        )
    db.info["untrusted_movie_ids"] = frozenset(movie_ids)
    return movie_ids


def trusted_movie_query(db: Session, query: Query | None = None) -> Query:
    query = query or db.query(Movie)
    excluded_ids = get_untrusted_movie_ids(db)
    if excluded_ids:
        query = query.filter(~Movie.id.in_(excluded_ids))
    return query


def is_trusted_movie(db: Session, movie_id: int) -> bool:
    return movie_id not in get_untrusted_movie_ids(db)


__all__ = ["get_untrusted_movie_ids", "is_trusted_movie", "trusted_movie_query"]
