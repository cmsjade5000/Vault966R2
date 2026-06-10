"""Audit database integrity and reconcile imported movies with their staged source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import random
import re
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, selectinload

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api.models  # noqa: E402,F401
from api.models.movie import Movie, MovieIngestProvenance  # noqa: E402
from api.models.person import Role, RoleType  # noqa: E402
from api.models.source_sync import SourceFieldDecision  # noqa: E402
from api.services.source_sync import parse_directors  # noqa: E402
from api.utils.providers import split_providers  # noqa: E402
from core.genres import split_and_normalize  # noqa: E402
from core.movie_metadata import MovieMetadata  # noqa: E402

DEFAULT_SOURCE = ROOT / "data" / "import" / "legacy" / "Vault966_MovieDB_20250724_v03.staged.csv"
DEFAULT_OUTPUT = (
    ROOT / "data" / "import" / "legacy" / "Vault966_MovieDB_20250724_v03.integrity.json"
)
TITLE_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _movie_record(movie: Movie) -> dict[str, Any]:
    directors = [
        role.person.name
        for role in sorted(movie.roles, key=lambda item: item.billing_order or 0)
        if role.role_type == RoleType.DIRECTOR
    ]
    cast = [
        role.person.name
        for role in sorted(movie.roles, key=lambda item: item.billing_order or 0)
        if role.role_type == RoleType.ACTOR
    ]
    return {
        "vault_id": movie.vault_id,
        "title": _clean(movie.title),
        "year": movie.year,
        "runtime": movie.runtime,
        "plot": _clean(movie.plot),
        "awards": _clean(movie.awards),
        "certificate": _clean(movie.certificate),
        "imdb_id": _clean(movie.imdb_id),
        "tmdb_id": movie.tmdb_id,
        "imdb_rating": movie.imdb_rating,
        "imdb_votes": movie.imdb_votes,
        "rt_score": movie.rt_score,
        "poster_url": _clean(movie.poster_url),
        "genres": sorted(
            split_and_normalize([genre.name for genre in movie.genres]), key=str.casefold
        ),
        "keywords": sorted(list(movie.keywords or []), key=str.casefold),
        "directors": directors,
        "cast": cast,
        "where_to_watch": sorted(split_providers(movie.where_to_watch), key=str.casefold),
        "collection": _clean(movie.collection),
    }


def _source_record(row: dict[str, Any]) -> dict[str, Any]:
    metadata = MovieMetadata.from_mapping(row)
    return {
        "title": _clean(metadata.title),
        "year": metadata.year,
        "runtime": metadata.runtime,
        "plot": _clean(metadata.plot),
        "awards": _clean(metadata.awards),
        "certificate": _clean(metadata.certificate),
        "imdb_id": _clean(metadata.imdb_id),
        "tmdb_id": metadata.tmdb_id,
        "imdb_rating": metadata.imdb_rating,
        "imdb_votes": metadata.imdb_votes,
        "rt_score": metadata.rt_score,
        "poster_url": _clean(metadata.poster_url),
        "genres": sorted(metadata.genres, key=str.casefold),
        "keywords": sorted(metadata.keywords, key=str.casefold),
        "directors": metadata.directors,
        "cast": metadata.cast,
        "where_to_watch": sorted(metadata.where_to_watch, key=str.casefold),
        "collection": _clean(metadata.collection),
    }


def _fingerprint(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_source(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        str(row["vault_id"]).strip(): _source_record(row)
        for row in rows
        if str(row.get("vault_id") or "").strip()
    }


def _approved_source_decisions(
    db: Session,
) -> dict[tuple[int, str], SourceFieldDecision]:
    latest: dict[tuple[int, str], SourceFieldDecision] = {}
    decisions = (
        db.query(SourceFieldDecision)
        .options(selectinload(SourceFieldDecision.source_row))
        .filter(SourceFieldDecision.undone_at.is_(None))
        .order_by(
            SourceFieldDecision.decided_at.desc(),
            SourceFieldDecision.id.desc(),
        )
        .all()
    )
    for decision in decisions:
        latest.setdefault((decision.movie_id, decision.field_name), decision)
    return {key: decision for key, decision in latest.items() if decision.decision == "use_source"}


def _decision_matches_actual(
    decision: SourceFieldDecision,
    *,
    audit_field: str,
    actual_value: Any,
) -> bool:
    row = decision.source_row
    if audit_field == "title":
        return _clean(row.title) == actual_value
    if audit_field == "year":
        return row.year == actual_value
    if audit_field == "runtime":
        return row.runtime == actual_value
    if audit_field == "directors":
        approved = sorted(parse_directors(row.director), key=str.casefold)
        current = sorted(actual_value, key=str.casefold)
        return approved == current
    return False


def _duplicates(db: Session, column) -> list[dict[str, Any]]:
    rows = (
        db.query(column, func.count(Movie.id))
        .filter(column.isnot(None))
        .group_by(column)
        .having(func.count(Movie.id) > 1)
        .all()
    )
    return [{"value": value, "count": count} for value, count in rows]


def audit(
    db: Session,
    *,
    source_path: pathlib.Path | None = None,
    sample_size: int = 20,
    sample_seed: int = 966,
) -> dict[str, Any]:
    movies = (
        db.query(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.roles).selectinload(Role.person),
            selectinload(Movie.ingest_provenance),
        )
        .order_by(Movie.id)
        .all()
    )
    records = [{"id": movie.id, **_movie_record(movie)} for movie in movies]
    provenance_by_movie = {
        provenance.movie_id: provenance
        for provenance in db.query(MovieIngestProvenance)
        .filter(MovieIngestProvenance.provider == "legacy_vault_csv")
        .all()
    }

    structural = {
        "duplicate_imdb_ids": _duplicates(db, Movie.imdb_id),
        "duplicate_tmdb_ids": _duplicates(db, Movie.tmdb_id),
        "missing_titles": [movie.id for movie in movies if not str(movie.title or "").strip()],
        "invalid_years": [
            movie.id
            for movie in movies
            if movie.year is not None and not 1870 <= movie.year <= 2100
        ],
        "invalid_runtimes": [
            movie.id for movie in movies if movie.runtime is not None and movie.runtime <= 0
        ],
        "missing_provenance": [movie.id for movie in movies if not movie.ingest_provenance],
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
    structural_issue_count = sum(len(items) for items in structural.values())
    content_review = {
        "title_embedded_year_conflicts": [
            {
                "movie_id": movie.id,
                "title": movie.title,
                "database_year": movie.year,
                "embedded_year": int(match.group(1)),
            }
            for movie in movies
            if (match := TITLE_YEAR_RE.search(movie.title or ""))
            and movie.year is not None
            and int(match.group(1)) != movie.year
        ],
        "missing_year": [
            {"movie_id": movie.id, "title": movie.title} for movie in movies if movie.year is None
        ],
        "missing_external_ids": [
            {"movie_id": movie.id, "title": movie.title, "year": movie.year}
            for movie in movies
            if movie.imdb_id is None and movie.tmdb_id is None
        ],
    }
    content_review_issue_count = sum(len(items) for items in content_review.values())

    drift: list[dict[str, Any]] = []
    approved_deviations: list[dict[str, Any]] = []
    missing_source_ids: list[dict[str, Any]] = []
    source_unmatched: list[str] = []
    source = _load_source(source_path) if source_path is not None else {}
    approved_decisions = _approved_source_decisions(db)
    matched_source_ids: set[str] = set()
    for movie in movies:
        provenance = provenance_by_movie.get(movie.id)
        vault_id = movie.vault_id or (provenance.provider_id if provenance else None)
        if not vault_id:
            continue
        expected = source.get(vault_id)
        if expected is None:
            missing_source_ids.append(
                {"movie_id": movie.id, "vault_id": vault_id, "title": movie.title}
            )
            continue
        matched_source_ids.add(vault_id)
        actual = _movie_record(movie)
        raw_differences = {
            field: {"source": expected[field], "database": actual[field]}
            for field in expected
            if expected[field] != actual[field]
        }
        differences: dict[str, Any] = {}
        approved: dict[str, Any] = {}
        for field, values in raw_differences.items():
            decision_field = "director" if field == "directors" else field
            decision = approved_decisions.get((movie.id, decision_field))
            if decision is not None and _decision_matches_actual(
                decision,
                audit_field=field,
                actual_value=actual[field],
            ):
                approved[field] = {
                    **values,
                    "decision_id": decision.id,
                    "source_snapshot_id": decision.source_row.snapshot_id,
                }
            else:
                differences[field] = values
        if differences:
            drift.append(
                {
                    "movie_id": movie.id,
                    "vault_id": vault_id,
                    "title": movie.title,
                    "differences": differences,
                }
            )
        if approved:
            approved_deviations.append(
                {
                    "movie_id": movie.id,
                    "vault_id": vault_id,
                    "title": movie.title,
                    "differences": approved,
                }
            )
    if source:
        source_unmatched = sorted(set(source) - matched_source_ids)

    rng = random.Random(sample_seed)
    identified = [movie for movie in movies if movie.imdb_id or movie.tmdb_id]
    unidentified = [movie for movie in movies if not movie.imdb_id and not movie.tmdb_id]
    sample: list[Movie] = []
    unidentified_quota = min(len(unidentified), max(1, sample_size // 5))
    identified_quota = min(len(identified), max(0, sample_size - unidentified_quota))
    if identified_quota:
        sample.extend(rng.sample(identified, identified_quota))
    if unidentified_quota:
        sample.extend(rng.sample(unidentified, unidentified_quota))
    sample.sort(key=lambda movie: movie.id)

    field_coverage = {
        field: sum(bool(record.get(field)) for record in records)
        for field in (
            "year",
            "runtime",
            "plot",
            "poster_url",
            "certificate",
            "keywords",
            "imdb_id",
            "tmdb_id",
            "genres",
            "directors",
            "cast",
        )
    }
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "movie_count": len(movies),
            "structural_issue_count": structural_issue_count,
            "content_review_issue_count": content_review_issue_count,
            "source_drift_count": len(drift),
            "approved_source_deviation_count": len(approved_deviations),
            "missing_source_id_count": len(missing_source_ids),
            "source_unmatched_count": len(source_unmatched),
            "healthy": structural_issue_count == 0 and not drift and not missing_source_ids,
            "review_required": content_review_issue_count > 0 or bool(source_unmatched),
        },
        "collection_fingerprint": _fingerprint(records),
        "field_coverage": field_coverage,
        "structural": structural,
        "content_review": content_review,
        "source_reconciliation": {
            "source_path": str(source_path) if source_path is not None else None,
            "drift": drift,
            "approved_deviations": approved_deviations,
            "missing_source_ids": missing_source_ids,
            "source_unmatched_vault_ids": source_unmatched,
        },
        "spot_check": [
            {
                "movie_id": movie.id,
                "vault_id": movie.vault_id
                or (
                    provenance_by_movie.get(movie.id).provider_id
                    if provenance_by_movie.get(movie.id)
                    else None
                ),
                **_movie_record(movie),
            }
            for movie in sample
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="sqlite:///./vault.db")
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--baseline", type=pathlib.Path)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--sample-seed", type=int, default=966)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    with Session(engine) as db:
        report = audit(
            db,
            source_path=args.source,
            sample_size=max(0, args.sample_size),
            sample_seed=args.sample_seed,
        )

    if args.baseline and args.baseline.exists():
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        report["baseline_comparison"] = {
            "baseline_path": str(args.baseline),
            "fingerprint_changed": baseline.get("collection_fingerprint")
            != report["collection_fingerprint"],
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], sort_keys=True))
    print(f"Collection fingerprint: {report['collection_fingerprint']}")
    print(f"Report: {args.output}")
    return 0 if report["summary"]["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
