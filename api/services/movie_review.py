from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.models.movie_review import MovieReviewCheck

TITLE_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


@dataclass(frozen=True)
class ReviewIssue:
    issue_type: str
    label: str
    detail: str
    fingerprint: str
    priority: int


@dataclass(frozen=True)
class MovieReviewItem:
    movie: Movie
    issues: tuple[ReviewIssue, ...]


def _fingerprint(*values: object) -> str:
    serialized = "\x1f".join("" if value is None else str(value) for value in values)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def detect_review_issues(movie: Movie) -> tuple[ReviewIssue, ...]:
    issues: list[ReviewIssue] = []
    title_match = TITLE_YEAR_RE.search(movie.title or "")
    title_year = int(title_match.group(1)) if title_match else None

    if title_year is not None and movie.year is not None and title_year != movie.year:
        issues.append(
            ReviewIssue(
                issue_type="title_year_conflict",
                label="Title and year disagree",
                detail=f"The title says {title_year}, but the year field says {movie.year}.",
                fingerprint=_fingerprint(
                    "title_year_conflict",
                    movie.title,
                    movie.year,
                    movie.imdb_id,
                    movie.tmdb_id,
                ),
                priority=1,
            )
        )

    if movie.year is None:
        issues.append(
            ReviewIssue(
                issue_type="missing_year",
                label="Year is missing",
                detail="Confirm the release year for this movie.",
                fingerprint=_fingerprint(
                    "missing_year",
                    movie.title,
                    movie.year,
                    movie.imdb_id,
                    movie.tmdb_id,
                ),
                priority=2,
            )
        )

    if not movie.imdb_id and movie.tmdb_id is None:
        issues.append(
            ReviewIssue(
                issue_type="missing_external_ids",
                label="No source IDs",
                detail="Neither an IMDb ID nor a TMDB ID is attached.",
                fingerprint=_fingerprint(
                    "missing_external_ids",
                    movie.title,
                    movie.year,
                    movie.imdb_id,
                    movie.tmdb_id,
                ),
                priority=3,
            )
        )

    return tuple(sorted(issues, key=lambda issue: issue.priority))


def get_review_queue(db: Session) -> tuple[list[MovieReviewItem], int]:
    reviewed = {
        (row.movie_id, row.issue_type, row.issue_fingerprint)
        for row in db.query(MovieReviewCheck).all()
    }
    queue: list[MovieReviewItem] = []
    finding_count = 0

    for movie in db.query(Movie).order_by(Movie.vault_id.asc(), Movie.id.asc()).all():
        issues = detect_review_issues(movie)
        finding_count += len(issues)
        open_issues = tuple(
            issue
            for issue in issues
            if (movie.id, issue.issue_type, issue.fingerprint) not in reviewed
        )
        if open_issues:
            queue.append(MovieReviewItem(movie=movie, issues=open_issues))

    queue.sort(
        key=lambda item: (
            min(issue.priority for issue in item.issues),
            item.movie.vault_id or "",
            item.movie.id,
        )
    )
    return queue, finding_count


def record_review_decision(
    db: Session,
    *,
    movie: Movie,
    issues: tuple[ReviewIssue, ...],
    decision: str,
    profile_id: int | None,
) -> None:
    for issue in issues:
        existing = (
            db.query(MovieReviewCheck)
            .filter(MovieReviewCheck.movie_id == movie.id)
            .filter(MovieReviewCheck.issue_type == issue.issue_type)
            .filter(MovieReviewCheck.issue_fingerprint == issue.fingerprint)
            .one_or_none()
        )
        if existing is None:
            db.add(
                MovieReviewCheck(
                    movie_id=movie.id,
                    issue_type=issue.issue_type,
                    issue_fingerprint=issue.fingerprint,
                    decision=decision,
                    checked_by_profile_id=profile_id,
                )
            )
    db.commit()
