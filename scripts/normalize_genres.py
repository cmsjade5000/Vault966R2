"""Normalize movie genres by splitting composite labels and applying synonyms.

Related skill: `genre-mood-normalizer`.

Dry run:
  python scripts/normalize_genres.py --report reports/genre_normalization.csv

Apply updates:
  python scripts/normalize_genres.py --apply --cleanup
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
from api.models.movie import Genre, Movie, movie_genres  # noqa: E402
from api.models.person import Role  # noqa: F401,E402  # ensure mapper registration
from core.genres import split_and_normalize  # noqa: E402

DEFAULT_REPORT = ROOT_DIR / "reports" / "genre_normalization.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize movie genres.")
    parser.add_argument("--limit", type=int, default=0, help="Max movies to process.")
    parser.add_argument("--apply", action="store_true", help="Apply updates to the database.")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete unused genre rows after normalization (requires --apply).",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help=f"CSV report output path (default: {DEFAULT_REPORT}).",
    )
    return parser.parse_args()


def ensure_genres(db: Session, labels: Iterable[str]) -> dict[str, Genre]:
    existing = {row.name: row for row in db.query(Genre).all()}
    for label in labels:
        if label in existing:
            continue
        genre = Genre(name=label)
        db.add(genre)
        existing[label] = genre
    db.flush()
    return existing


def _genres_for_movie(movie: Movie) -> List[str]:
    return [genre.name for genre in movie.genres if getattr(genre, "name", None)]


def write_report(path: pathlib.Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "movie_id",
        "title",
        "before_genres",
        "after_genres",
        "action",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def cleanup_unused_genres(db: Session) -> int:
    unused = (
        db.query(Genre)
        .outerjoin(movie_genres, Genre.id == movie_genres.c.genre_id)
        .filter(movie_genres.c.movie_id.is_(None))
        .all()
    )
    removed = 0
    for genre in unused:
        db.delete(genre)
        removed += 1
    return removed


def main() -> int:
    args = parse_args()
    report_path = pathlib.Path(args.report)
    results = []

    with SessionLocal() as db:
        query = db.query(Movie).options(selectinload(Movie.genres))
        if args.limit:
            query = query.limit(args.limit)

        all_labels: list[str] = []
        for movie in query.all():
            current = _genres_for_movie(movie)
            normalized = split_and_normalize(current)
            if normalized:
                all_labels.extend(normalized)

        genre_by_name = ensure_genres(db, sorted(set(all_labels)))

        updated = 0
        unchanged = 0
        empty = 0

        query = db.query(Movie).options(selectinload(Movie.genres))
        if args.limit:
            query = query.limit(args.limit)

        for movie in query.all():
            current = _genres_for_movie(movie)
            normalized = split_and_normalize(current)
            if not normalized:
                empty += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "before_genres": ", ".join(current),
                        "after_genres": "",
                        "action": "no-genres",
                    }
                )
                continue

            if set(current) == set(normalized):
                unchanged += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "title": movie.title,
                        "before_genres": ", ".join(current),
                        "after_genres": ", ".join(normalized),
                        "action": "unchanged",
                    }
                )
                continue

            if args.apply:
                movie.genres = [genre_by_name[name] for name in normalized]
                db.add(movie)
            updated += 1
            results.append(
                {
                    "movie_id": movie.id,
                    "title": movie.title,
                    "before_genres": ", ".join(current),
                    "after_genres": ", ".join(normalized),
                    "action": "updated" if args.apply else "planned",
                }
            )

        if args.apply:
            db.commit()

        removed = 0
        if args.apply and args.cleanup:
            removed = cleanup_unused_genres(db)
            db.commit()

    write_report(report_path, results)
    print(f"report: {report_path}")
    print(f"updated: {updated}, unchanged: {unchanged}, no-genres: {empty}")
    if args.apply and args.cleanup:
        print(f"removed unused genres: {removed}")
    if not args.apply:
        print("dry run only: use --apply to write changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
