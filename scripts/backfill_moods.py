"""Backfill movie moods using deterministic, explainable rules.

Related skill: `genre-mood-normalizer`.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import pathlib
import sys
from typing import Iterable, List

from sqlalchemy.orm import Session, selectinload

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Mood, Movie, movie_moods  # noqa: E402
from api.models.person import Role  # noqa: F401,E402  # ensure mapper registration
from core.moods import (  # noqa: E402
    DEFAULT_MAX_MOODS,
    DEFAULT_MIN_SCORE,
    MOOD_TAXONOMY,
    analyze_moods,
)
from scripts.backfill_db_backup import backup_active_sqlite_database  # noqa: E402

DEFAULT_REPORT = ROOT_DIR / "reports" / "mood_backfill.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill movie moods from metadata signals.")
    parser.add_argument("--limit", type=int, default=0, help="Max movies to process (0 = all).")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing moods (default: skip if moods already set).",
    )
    parser.add_argument(
        "--cleanup-unused",
        action="store_true",
        help="Delete unused mood rows after applying changes.",
    )
    parser.add_argument(
        "--max-moods",
        type=int,
        default=DEFAULT_MAX_MOODS,
        help=f"Maximum moods to assign per movie (default: {DEFAULT_MAX_MOODS}).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=DEFAULT_MIN_SCORE,
        help=f"Minimum score threshold for mood assignment (default: {DEFAULT_MIN_SCORE}).",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help=f"CSV report output path (default: {DEFAULT_REPORT}).",
    )
    return parser.parse_args()


def ensure_mood_rows(db: Session) -> dict[str, Mood]:
    existing = {row.name: row for row in db.query(Mood).all()}
    for name, meta in MOOD_TAXONOMY.items():
        if name in existing:
            existing[name].description = meta.get("description")
            continue
        mood = Mood(name=name, description=meta.get("description"), emoji=meta.get("emoji"))
        db.add(mood)
        existing[name] = mood
    db.flush()
    return existing


def _genres_for_movie(movie: Movie) -> List[str]:
    return [genre.name for genre in movie.genres if getattr(genre, "name", None)]


def _join(values: Iterable[object]) -> str:
    return ", ".join(str(value) for value in values if value not in (None, ""))


def _keywords_for_report(raw: object | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, dict):
        values: list[str] = []
        for value in raw.values():
            values.extend(_keywords_for_report(value))
        return values
    if isinstance(raw, list):
        values = []
        for value in raw:
            values.extend(_keywords_for_report(value))
        return values
    return [str(raw)]


def write_report(path: pathlib.Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "movie_id",
        "title",
        "genres",
        "keywords",
        "certificate",
        "runtime",
        "existing_moods",
        "computed_moods",
        "confidence",
        "score",
        "evidence",
        "candidate_scores",
        "avoidance_flags",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def cleanup_unused_moods(db: Session) -> int:
    unused = (
        db.query(Mood)
        .outerjoin(movie_moods, Mood.id == movie_moods.c.mood_id)
        .filter(movie_moods.c.movie_id.is_(None))
        .all()
    )
    count = len(unused)
    for mood in unused:
        db.delete(mood)
    return count


def main() -> int:
    args = parse_args()
    report_path = pathlib.Path(args.report)
    results = []

    if args.apply:
        backup = backup_active_sqlite_database("mood backfill", now=datetime.now(timezone.utc))
        print(f"backup: {backup.backup}")

    with SessionLocal() as db:
        mood_by_name = ensure_mood_rows(db) if args.apply else {}
        query = db.query(Movie).options(
            selectinload(Movie.genres),
            selectinload(Movie.moods),
        ).order_by(Movie.id)
        if args.limit:
            query = query.limit(args.limit)

        updated = 0
        skipped = 0
        unmatched = 0
        unchanged = 0
        removed_unused = 0

        for movie in query.all():
            existing = [mood.name for mood in movie.moods]
            genres = _genres_for_movie(movie)
            if existing and not args.force:
                skipped += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "genres": _join(genres),
                        "keywords": _join(_keywords_for_report(movie.keywords)),
                        "certificate": movie.certificate or "",
                        "runtime": movie.runtime or "",
                        "existing_moods": _join(existing),
                        "computed_moods": "",
                        "confidence": "",
                        "score": "",
                        "evidence": "",
                        "candidate_scores": "",
                        "avoidance_flags": "",
                        "action": "skipped",
                    }
                )
                continue

            analysis = analyze_moods(
                genres,
                keywords=movie.keywords,
                plot=movie.plot,
                certificate=movie.certificate,
                runtime=movie.runtime,
                max_moods=args.max_moods,
                min_score=args.min_score,
            )
            computed = list(analysis.labels)
            selected_scores = [str(item.score) for item in analysis.selected]
            confidence = [item.confidence for item in analysis.selected]
            evidence = [f"{item.mood}={item.explanation}" for item in analysis.selected]
            candidate_scores = [f"{item.mood}:{item.score}" for item in analysis.candidates]

            if not computed:
                unmatched += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "genres": _join(genres),
                        "keywords": _join(_keywords_for_report(movie.keywords)),
                        "certificate": movie.certificate or "",
                        "runtime": movie.runtime or "",
                        "existing_moods": _join(existing),
                        "computed_moods": "",
                        "confidence": "",
                        "score": "",
                        "evidence": "",
                        "candidate_scores": _join(candidate_scores),
                        "avoidance_flags": _join(analysis.avoidance_flags),
                        "action": "no-match",
                    }
                )
                continue

            if existing == computed:
                unchanged += 1
                action = "unchanged"
            else:
                updated += 1
                action = "updated" if args.apply else "planned"

            if args.apply:
                movie.moods = [mood_by_name[name] for name in computed]
                db.add(movie)
            results.append(
                {
                    "movie_id": movie.id,
                    "title": movie.title,
                    "genres": _join(genres),
                        "keywords": _join(_keywords_for_report(movie.keywords)),
                    "certificate": movie.certificate or "",
                    "runtime": movie.runtime or "",
                    "existing_moods": _join(existing),
                    "computed_moods": _join(computed),
                    "confidence": _join(confidence),
                    "score": _join(selected_scores),
                    "evidence": " | ".join(evidence),
                    "candidate_scores": _join(candidate_scores),
                    "avoidance_flags": _join(analysis.avoidance_flags),
                    "action": action,
                }
            )

        if args.apply:
            db.flush()
            if args.cleanup_unused:
                removed_unused = cleanup_unused_moods(db)
            db.commit()

    write_report(report_path, results)
    print(f"report: {report_path}")
    summary = (
        f"updated: {updated}, unchanged: {unchanged}, skipped: {skipped}, "
        f"no-match: {unmatched}"
    )
    if args.apply and args.cleanup_unused:
        summary += f", removed-unused-moods: {removed_unused}"
    print(summary)
    if not args.apply:
        print("dry run only: use --apply to write changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
