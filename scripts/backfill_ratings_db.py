#!/usr/bin/env python3
"""Backfill IMDb/RT ratings for movies missing scores via OMDb.

Related skill: `metadata-cleanup`.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import pathlib
import sys

import httpx
from sqlalchemy import or_

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config import settings  # noqa: E402
from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: F401,E402  # ensure mapper registration
from api.utils.omdb import (
    extract_rotten_tomatoes_score,
    parse_imdb_rating,
    parse_imdb_votes,
)  # noqa: E402

DEFAULT_REPORT = ROOT_DIR / "reports" / "ratings_backfill.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill IMDb/RT ratings for movies missing scores.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max movies to process (0 = all).")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    parser.add_argument(
        "--omdb-key",
        default=None,
        help="OMDb API key (default: env OMDB_API_KEY or settings).",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help=f"CSV report output path (default: {DEFAULT_REPORT}).",
    )
    return parser.parse_args()


def fetch_omdb(client: httpx.Client, api_key: str, imdb_id: str) -> dict | None:
    resp = client.get(
        "https://www.omdbapi.com/",
        params={"apikey": api_key, "i": imdb_id},
        timeout=12.0,
    )
    if resp.status_code != 200:
        return None
    payload = resp.json()
    if not isinstance(payload, dict):
        return None
    if payload.get("Response") == "False":
        return None
    return payload


def write_report(path: pathlib.Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "movie_id",
        "imdb_id",
        "title",
        "imdb_rating",
        "imdb_votes",
        "rt_score",
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
    api_key = args.omdb_key or os.getenv("OMDB_API_KEY") or settings.omdb_api_key
    if not api_key:
        raise SystemExit("OMDB_API_KEY is missing (set env var or pass --omdb-key).")

    results: list[dict[str, object]] = []
    updated = 0
    skipped = 0
    missing = 0
    now = datetime.datetime.now(datetime.timezone.utc)

    with SessionLocal() as db, httpx.Client() as client:
        query = db.query(Movie).filter(
            Movie.imdb_id.isnot(None),
            Movie.imdb_id != "",
            or_(
                Movie.imdb_rating.is_(None),
                Movie.imdb_votes.is_(None),
                Movie.rt_score.is_(None),
            ),
        )
        if args.limit:
            query = query.limit(args.limit)

        for movie in query.all():
            payload = fetch_omdb(client, api_key, movie.imdb_id or "")
            if not payload:
                missing += 1
                results.append(
                    {
                        "movie_id": movie.id,
                        "imdb_id": movie.imdb_id,
                        "title": movie.title,
                        "imdb_rating": movie.imdb_rating,
                        "imdb_votes": movie.imdb_votes,
                        "rt_score": movie.rt_score,
                        "action": "no-match",
                    }
                )
                continue

            imdb_rating = parse_imdb_rating(payload.get("imdbRating"))
            imdb_votes = parse_imdb_votes(payload.get("imdbVotes"))
            rt_score = extract_rotten_tomatoes_score(payload)

            changed = False
            if movie.imdb_rating is None and imdb_rating is not None:
                movie.imdb_rating = imdb_rating
                changed = True
            if movie.imdb_votes is None and imdb_votes is not None:
                movie.imdb_votes = imdb_votes
                changed = True
            if movie.rt_score is None and rt_score is not None:
                movie.rt_score = rt_score
                changed = True

            if changed:
                if args.apply:
                    movie.last_omdb_fetch_at = now
                    db.add(movie)
                updated += 1
                action = "updated" if args.apply else "planned"
            else:
                skipped += 1
                action = "skipped"

            results.append(
                {
                    "movie_id": movie.id,
                    "imdb_id": movie.imdb_id,
                    "title": movie.title,
                    "imdb_rating": movie.imdb_rating or imdb_rating,
                    "imdb_votes": movie.imdb_votes or imdb_votes,
                    "rt_score": movie.rt_score or rt_score,
                    "action": action,
                }
            )

        if args.apply:
            db.commit()

    write_report(report_path, results)
    print(f"report: {report_path}")
    print(f"updated: {updated}, skipped: {skipped}, no-match: {missing}")
    if not args.apply:
        print("dry run only: use --apply to write changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
