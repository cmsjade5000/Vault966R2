"""Backfill movie moods using deterministic genre rules.

Related skill: `genre-mood-normalizer`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
from typing import Iterable, List

from sqlalchemy.orm import Session, selectinload

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Mood, Movie  # noqa: E402
from api.models.person import Role  # noqa: F401,E402  # ensure mapper registration
from core.moods import MOOD_TAXONOMY, score_moods  # noqa: E402

DEFAULT_REPORT = ROOT_DIR / "reports" / "mood_backfill.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill movie moods from genres.")
    parser.add_argument("--limit", type=int, default=0, help="Max movies to process (0 = all).")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing moods (default: skip if moods already set).",
    )
    parser.add_argument(
        "--max-moods",
        type=int,
        default=1,
        help="Maximum moods to assign per movie (default: 1).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=1,
        help="Minimum score threshold for mood assignment (default: 1).",
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
            continue
        mood = Mood(name=name, description=meta.get("description"))
        db.add(mood)
        existing[name] = mood
    db.flush()
    return existing


def _genres_for_movie(movie: Movie) -> List[str]:
    return [genre.name for genre in movie.genres if getattr(genre, "name", None)]


def write_report(path: pathlib.Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "movie_id",
        "title",
        "genres",
        "existing_moods",
        "computed_moods",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    report_path = pathlib.Path(args.report)
    results = []

    with SessionLocal() as db:
        mood_by_name = ensure_mood_rows(db)
        query = db.query(Movie).options(
            selectinload(Movie.genres),
            selectinload(Movie.moods),
        )
        if args.limit:
            query = query.limit(args.limit)

        updated = 0
        skipped = 0
        unmatched = 0

        for movie in query.all():
            existing = [mood.name for mood in movie.moods]
            if existing and not args.force:
                skipped += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "genres": ", ".join(_genres_for_movie(movie)),
                        "existing_moods": ", ".join(existing),
                        "computed_moods": "",
                        "action": "skipped",
                    }
                )
                continue

            computed = score_moods(
                _genres_for_movie(movie),
                max_moods=args.max_moods,
                min_score=args.min_score,
            )
            if not computed:
                unmatched += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "genres": ", ".join(_genres_for_movie(movie)),
                        "existing_moods": ", ".join(existing),
                        "computed_moods": "",
                        "action": "no-match",
                    }
                )
                continue

            if args.apply:
                movie.moods = [mood_by_name[name] for name in computed]
                db.add(movie)
            updated += 1
            results.append(
                {
                    "movie_id": movie.id,
                    "title": movie.title,
                    "genres": ", ".join(_genres_for_movie(movie)),
                    "existing_moods": ", ".join(existing),
                    "computed_moods": ", ".join(computed),
                    "action": "updated" if args.apply else "planned",
                }
            )

        if args.apply:
            db.commit()

    write_report(report_path, results)
    print(f"report: {report_path}")
    print(f"updated: {updated}, skipped: {skipped}, no-match: {unmatched}")
    if not args.apply:
        print("dry run only: use --apply to write changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
