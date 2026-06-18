from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from pathlib import Path
from threading import Lock
from typing import TypeAlias

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session, selectinload

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.movie_review import MovieReviewCheck
from api.models.person import Role
from api.models.source_sync import (
    SourceFieldDecision,
    SourceMovieRow,
    SourceReconciliationMatch,
)
from api.services.movie_review import detect_review_issues, get_review_queue
from api.services.source_sync import (
    get_source_review_queue,
    latest_active_snapshot,
    source_row_conflicts,
)

DatabaseRevision: TypeAlias = tuple[str, int, int, int, int]

_process_cache_lock = Lock()
_process_untrusted_cache: tuple[DatabaseRevision, frozenset[int]] | None = None


def invalidate_untrusted_movie_cache(db: Session | None = None) -> None:
    global _process_untrusted_cache
    if db is not None:
        db.info.pop("untrusted_movie_ids", None)
    with _process_cache_lock:
        _process_untrusted_cache = None


def _database_revision(db: Session) -> DatabaseRevision | None:
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return None
    database = bind.url.database
    if not database or database == ":memory:":
        return None

    path = Path(database).resolve()
    wal_path = Path(f"{path}-wal")

    try:
        database_stat = path.stat()
    except OSError:
        return None
    try:
        wal_stat = wal_path.stat()
    except OSError:
        wal_mtime_ns = 0
        wal_size = 0
    else:
        wal_mtime_ns = wal_stat.st_mtime_ns
        wal_size = wal_stat.st_size

    return (
        str(path),
        database_stat.st_mtime_ns,
        database_stat.st_size,
        wal_mtime_ns,
        wal_size,
    )


def _get_process_cached_untrusted_ids(
    revision: DatabaseRevision | None,
) -> set[int] | None:
    if revision is None:
        return None
    with _process_cache_lock:
        if _process_untrusted_cache is None:
            return None
        cached_revision, cached_ids = _process_untrusted_cache
        return set(cached_ids) if cached_revision == revision else None


def _set_process_cached_untrusted_ids(
    revision: DatabaseRevision | None,
    movie_ids: set[int],
) -> None:
    global _process_untrusted_cache
    if revision is None:
        return
    with _process_cache_lock:
        _process_untrusted_cache = (revision, frozenset(movie_ids))


def _get_scoped_untrusted_movie_ids(db: Session, movie_ids: set[int]) -> set[int]:
    if not movie_ids:
        return set()

    untrusted_ids = {
        movie_id
        for (movie_id,) in db.query(MovieFlag.movie_id)
        .filter(MovieFlag.movie_id.in_(movie_ids))
        .all()
    }

    reviewed = {
        (row.movie_id, row.issue_type, row.issue_fingerprint)
        for row in db.query(MovieReviewCheck).filter(MovieReviewCheck.movie_id.in_(movie_ids)).all()
    }
    movies = db.query(Movie).filter(Movie.id.in_(movie_ids)).all()
    for movie in movies:
        if any(
            (movie.id, issue.issue_type, issue.fingerprint) not in reviewed
            for issue in detect_review_issues(movie)
        ):
            untrusted_ids.add(movie.id)

    snapshot = latest_active_snapshot(db)
    if snapshot is None:
        return untrusted_ids

    review_match_types = ("ambiguous", "duplicate", "source_only")
    rows = (
        db.query(SourceMovieRow)
        .join(SourceMovieRow.match)
        .options(
            selectinload(SourceMovieRow.match)
            .selectinload(SourceReconciliationMatch.movie)
            .selectinload(Movie.roles)
            .selectinload(Role.person)
        )
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .filter(
            or_(
                SourceReconciliationMatch.movie_id.in_(movie_ids),
                SourceReconciliationMatch.match_type.in_(review_match_types),
            )
        )
        .all()
    )
    matched_rows = [
        row
        for row in rows
        if row.match is not None
        and row.match.movie_id in movie_ids
        and row.match.match_type in {"exact", "likely", "manual"}
    ]
    decisions_by_row: dict[int, dict[str, SourceFieldDecision]] = defaultdict(dict)
    matched_row_ids = [row.id for row in matched_rows]
    if matched_row_ids:
        decisions = (
            db.query(SourceFieldDecision)
            .filter(SourceFieldDecision.source_row_id.in_(matched_row_ids))
            .filter(SourceFieldDecision.undone_at.is_(None))
            .order_by(
                SourceFieldDecision.source_row_id.asc(),
                SourceFieldDecision.decided_at.desc(),
                SourceFieldDecision.id.desc(),
            )
            .all()
        )
        for decision in decisions:
            decisions_by_row[decision.source_row_id].setdefault(decision.field_name, decision)

    for row in rows:
        match = row.match
        if match is None:
            continue
        if (
            match.movie_id in movie_ids
            and match.movie is not None
            and match.match_type in {"exact", "likely", "manual"}
            and source_row_conflicts(
                db,
                row,
                match.movie,
                decisions=decisions_by_row.get(row.id, {}),
            )
        ):
            untrusted_ids.add(match.movie_id)
        if match.match_type in review_match_types:
            untrusted_ids.update(movie_ids.intersection(match.candidate_movie_ids or ()))

    return untrusted_ids


def get_untrusted_movie_ids(db: Session, movie_ids: Collection[int] | None = None) -> set[int]:
    """Return movies with any unresolved identity or metadata review work."""
    if movie_ids is not None:
        scoped_ids = {movie_id for movie_id in movie_ids if movie_id > 0}
        return _get_scoped_untrusted_movie_ids(db, scoped_ids)

    cached = db.info.get("untrusted_movie_ids")
    if cached is not None:
        return set(cached)

    revision = _database_revision(db)
    process_cached = _get_process_cached_untrusted_ids(revision)
    if process_cached is not None:
        db.info["untrusted_movie_ids"] = frozenset(process_cached)
        return process_cached

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
    _set_process_cached_untrusted_ids(revision, movie_ids)
    return movie_ids


def trusted_movie_query(db: Session, query: Query | None = None) -> Query:
    query = query or db.query(Movie)
    excluded_ids = get_untrusted_movie_ids(db)
    if excluded_ids:
        query = query.filter(~Movie.id.in_(excluded_ids))
    return query


def is_trusted_movie(db: Session, movie_id: int) -> bool:
    return movie_id not in get_untrusted_movie_ids(db)


__all__ = [
    "get_untrusted_movie_ids",
    "invalidate_untrusted_movie_cache",
    "is_trusted_movie",
    "trusted_movie_query",
]
