from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Movie


def _duplicates(db: Session, column) -> list[dict[str, Any]]:
    rows = (
        db.query(column, func.count(Movie.id))
        .filter(column.isnot(None))
        .group_by(column)
        .having(func.count(Movie.id) > 1)
        .all()
    )
    return [{"value": value, "count": count} for value, count in rows]


def get_structural_issues(db: Session) -> dict[str, list[Any]]:
    return {
        "duplicate_imdb_ids": _duplicates(db, Movie.imdb_id),
        "duplicate_tmdb_ids": _duplicates(db, Movie.tmdb_id),
        "missing_titles": [
            movie_id
            for (movie_id,) in db.query(Movie.id)
            .filter(func.trim(func.coalesce(Movie.title, "")) == "")
            .all()
        ],
        "invalid_years": [
            movie_id
            for (movie_id,) in db.query(Movie.id)
            .filter(Movie.year.isnot(None))
            .filter((Movie.year < 1870) | (Movie.year > 2100))
            .all()
        ],
        "invalid_runtimes": [
            movie_id
            for (movie_id,) in db.query(Movie.id)
            .filter(Movie.runtime.isnot(None))
            .filter(Movie.runtime <= 0)
            .all()
        ],
        "missing_provenance": [
            movie.id for movie in db.query(Movie).all() if not movie.ingest_provenance
        ],
        "duplicate_title_year": [
            {"title": title, "year": year, "count": count}
            for title, year, count in (
                db.query(Movie.title, Movie.year, func.count(Movie.id))
                .group_by(func.lower(Movie.title), Movie.year)
                .having(func.count(Movie.id) > 1)
                .all()
            )
        ],
    }


def count_structural_issues(issues: dict[str, list[Any]]) -> int:
    return sum(len(items) for items in issues.values())


def get_structural_issue_count(db: Session) -> int:
    return count_structural_issues(get_structural_issues(db))


__all__ = [
    "count_structural_issues",
    "get_structural_issue_count",
    "get_structural_issues",
]
