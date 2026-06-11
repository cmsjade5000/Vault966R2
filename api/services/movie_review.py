from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
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


@dataclass(frozen=True)
class BulkReviewDecisionResult:
    movie_count: int
    finding_count: int
    flag_count: int


@dataclass(frozen=True)
class TitleYearCorrectionResult:
    movie_count: int
    cleared_flag_count: int


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


def title_year_from_title(title: str | None) -> int | None:
    match = TITLE_YEAR_RE.search(title or "")
    return int(match.group(1)) if match else None


def apply_title_year_authority(
    db: Session,
    *,
    movie: Movie,
    profile_id: int | None,
) -> bool:
    title_year = title_year_from_title(movie.title)
    if title_year is None or movie.year == title_year:
        return False

    conflict = next(
        (
            issue
            for issue in detect_review_issues(movie)
            if issue.issue_type == "title_year_conflict"
        ),
        None,
    )
    if conflict is not None:
        existing = (
            db.query(MovieReviewCheck)
            .filter(MovieReviewCheck.movie_id == movie.id)
            .filter(MovieReviewCheck.issue_type == conflict.issue_type)
            .filter(MovieReviewCheck.issue_fingerprint == conflict.fingerprint)
            .one_or_none()
        )
        if existing is None:
            db.add(
                MovieReviewCheck(
                    movie_id=movie.id,
                    issue_type=conflict.issue_type,
                    issue_fingerprint=conflict.fingerprint,
                    decision="title_year_applied",
                    checked_by_profile_id=profile_id,
                )
            )
        else:
            existing.decision = "title_year_applied"
            existing.checked_by_profile_id = profile_id

    movie.year = title_year
    if movie.flag is not None and movie.flag.reason == "Human review":
        remaining_notes = [
            note.strip()
            for note in (movie.flag.notes or "").split(";")
            if note.strip() and note.strip() != "Title and year disagree"
        ]
        if remaining_notes:
            movie.flag.notes = "; ".join(remaining_notes)
        else:
            db.delete(movie.flag)
    return True


def apply_all_title_year_corrections(
    db: Session,
    *,
    profile_id: int | None,
) -> TitleYearCorrectionResult:
    corrected = 0
    flags_before = db.query(MovieFlag).count()
    try:
        for movie in db.query(Movie).order_by(Movie.id).all():
            corrected += int(
                apply_title_year_authority(
                    db,
                    movie=movie,
                    profile_id=profile_id,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return TitleYearCorrectionResult(
        movie_count=corrected,
        cleared_flag_count=flags_before - db.query(MovieFlag).count(),
    )


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


def mark_all_review_items_needs_fix(
    db: Session,
    *,
    profile_id: int | None,
) -> BulkReviewDecisionResult:
    queue, _ = get_review_queue(db)
    finding_count = 0
    flag_count = 0

    try:
        for item in queue:
            movie = item.movie
            finding_count += len(item.issues)
            if movie.flag is None:
                db.add(
                    MovieFlag(
                        movie_id=movie.id,
                        reason="Human review",
                        notes="; ".join(issue.label for issue in item.issues),
                    )
                )
                flag_count += 1
            for issue in item.issues:
                db.add(
                    MovieReviewCheck(
                        movie_id=movie.id,
                        issue_type=issue.issue_type,
                        issue_fingerprint=issue.fingerprint,
                        decision="needs_fix",
                        checked_by_profile_id=profile_id,
                    )
                )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return BulkReviewDecisionResult(
        movie_count=len(queue),
        finding_count=finding_count,
        flag_count=flag_count,
    )
