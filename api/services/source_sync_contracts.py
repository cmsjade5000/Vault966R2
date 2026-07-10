from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.models.movie import Movie
    from api.models.source_sync import (
        SourceMovieRow,
        SourceReconciliationMatch,
        SourceSnapshot,
    )


class SourceSyncError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSourceRow:
    row_number: int
    title: str
    normalized_title: str
    runtime: int | None
    director: str | None
    normalized_directors: tuple[str, ...]
    year: int | None
    genre: str | None
    content_rating: str | None
    release_date: str | None
    hd: bool | None
    duplicate_group: str | None
    raw_data: dict[str, str]


@dataclass(frozen=True)
class SourceFieldConflict:
    field_name: str
    label: str
    source_value: str
    vault_value: str
    research: bool = False


@dataclass(frozen=True)
class ResearchLink:
    label: str
    url: str
    provider: str
    link_type: str


@dataclass(frozen=True)
class ResearchLinkSet:
    current: tuple[ResearchLink, ...]
    searches: tuple[ResearchLink, ...]
    search_title: str


@dataclass(frozen=True)
class SourceReviewItem:
    source_row: SourceMovieRow
    match: SourceReconciliationMatch
    movie: Movie | None
    conflicts: tuple[SourceFieldConflict, ...]
    candidate_movies: tuple[Movie, ...] = ()
    research_links: ResearchLinkSet | None = None
    candidate_research_links: dict[int, ResearchLinkSet] | None = None


@dataclass(frozen=True)
class BulkSourceDecisionResult:
    snapshot_id: int
    movie_count: int
    field_count: int
    skipped_field_count: int


@dataclass(frozen=True)
class FirstImportDecision:
    row: SourceMovieRow
    bucket: str
    reason: str
    candidate: dict | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class FirstImportAnalysis:
    snapshot_id: int
    auto_create: tuple[FirstImportDecision, ...]
    needs_review: tuple[FirstImportDecision, ...]
    duplicate_conflict: tuple[FirstImportDecision, ...]
    failed_lookup: tuple[FirstImportDecision, ...]

    @property
    def total_rows(self) -> int:
        return (
            len(self.auto_create)
            + len(self.needs_review)
            + len(self.duplicate_conflict)
            + len(self.failed_lookup)
        )


@dataclass(frozen=True)
class FirstImportApplyResult:
    snapshot_id: int
    created_count: int
    review_count: int
    duplicate_conflict_count: int
    failed_lookup_count: int
    created_movie_ids: tuple[int, ...]


@dataclass(frozen=True)
class FirstImportReport:
    snapshot: SourceSnapshot
    created_count: int
    review_count: int
    duplicate_conflict_count: int
    source_only_count: int

    @property
    def remaining_count(self) -> int:
        return self.review_count + self.duplicate_conflict_count + self.source_only_count


__all__ = [
    "BulkSourceDecisionResult",
    "FirstImportAnalysis",
    "FirstImportApplyResult",
    "FirstImportDecision",
    "FirstImportReport",
    "ParsedSourceRow",
    "ResearchLink",
    "ResearchLinkSet",
    "SourceFieldConflict",
    "SourceReviewItem",
    "SourceSyncError",
]
