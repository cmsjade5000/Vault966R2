"""Backfill missing backdrop URLs in the database using TMDb.

Related skill: `poster-backdrop-audit`.

Dry run:
  python scripts/backfill_backdrops.py --dry-run

Apply updates and write a report:
  python scripts/backfill_backdrops.py --report reports/backdrop_backfill.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys
import time
from typing import Any, Dict, Iterable, Optional

import httpx
from sqlalchemy import select

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config import settings  # noqa: E402
from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: E402,F401  # ensure mapper registration
from api.services import movie_lookup  # noqa: E402
from scripts.backfill_db_backup import backup_active_sqlite_database  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing movie backdrops")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of movies to process (default: 0 = no limit).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between API requests (default: 0.25).",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.72,
        help="Minimum TMDb match confidence for title-based lookups (default: 0.72).",
    )
    parser.add_argument(
        "--tmdb-key",
        default=None,
        help="TMDb API key (default: env TMDB_API_KEY).",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT_DIR / "reports" / "backdrop_backfill.csv"),
        help="CSV report output path (default: reports/backdrop_backfill.csv).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retry attempts for TMDb requests (default: 3).",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=0.6,
        help="Base backoff in seconds between retries (default: 0.6).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updates to the database.",
    )
    parser.add_argument(
        "--update-tmdb-id",
        action="store_true",
        help="Populate tmdb_id when missing and confidence meets the threshold.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log changes without writing to the database.",
    )
    return parser.parse_args()


def normalize_title(title: str) -> str:
    cleaned = title.strip().lower()
    cleaned = cleaned.replace("&", "and")
    return " ".join(cleaned.split())


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _year_delta(requested: Optional[int], candidate: Optional[int]) -> int:
    if requested is None or candidate is None:
        return 999
    return abs(requested - candidate)


def select_backdrop_candidate(
    requested_title: str,
    requested_year: Optional[int],
    candidates: Iterable[Dict[str, Any]],
    min_confidence: float,
) -> Optional[Dict[str, Any]]:
    scored: list[tuple[Dict[str, Any], float, bool, int, int]] = []
    for candidate in candidates:
        backdrop_url = candidate.get("backdrop_url")
        if not backdrop_url:
            continue
        confidence = _coerce_float(candidate.get("match_confidence"))
        if confidence < min_confidence:
            continue
        matched_title = candidate.get("matched_tmdb_title") or candidate.get("title") or ""
        match_exact = normalize_title(matched_title) == normalize_title(requested_title)
        matched_year = candidate.get("matched_tmdb_year") or candidate.get("year")
        delta = _year_delta(requested_year, matched_year)
        tmdb_id = int(candidate.get("tmdb_id") or 0)
        scored.append((candidate, confidence, match_exact, delta, tmdb_id))

    if not scored:
        return None

    scored.sort(key=lambda entry: (-entry[1], -int(entry[2]), entry[3], entry[4]))
    return scored[0][0]


def build_backdrop_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"https://image.tmdb.org/t/p/w780{path}"


def _with_retries(func, *, retries: int, backoff: float):
    attempt = 0
    while True:
        try:
            return func()
        except httpx.HTTPError:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(backoff * attempt)


def fetch_tmdb_detail(client: httpx.Client, api_key: str, tmdb_id: int) -> Dict[str, Any]:
    params = {
        "api_key": api_key,
        "append_to_response": "images",
    }
    response = client.get(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}",
        params=params,
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def extract_image_path(detail: Dict[str, Any]) -> Optional[str]:
    path = detail.get("backdrop_path")
    if path:
        return path
    images = detail.get("images")
    if not isinstance(images, dict):
        return None
    items = images.get("backdrops") or []
    if not isinstance(items, list):
        return None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file_path")
        if file_path:
            return file_path
    return None


def needs_backdrop(movie: Movie) -> bool:
    backdrop = (movie.backdrop_url or "").strip()
    return not backdrop


def write_report(path: pathlib.Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    api_key = args.tmdb_key or settings.tmdb_api_key or os.getenv("TMDB_API_KEY")
    if not api_key:
        raise SystemExit("TMDB_API_KEY is required to backfill backdrops")

    report_path = pathlib.Path(args.report)
    results = []
    updated = 0
    skipped = 0

    if args.apply and not args.dry_run:
        backup = backup_active_sqlite_database("backdrop backfill")
        print(f"backup: {backup.backup}")

    with SessionLocal() as db, httpx.Client(timeout=10.0) as client:
        query = select(Movie).where(Movie.backdrop_url.is_(None) | (Movie.backdrop_url == ""))
        if args.limit:
            query = query.limit(args.limit)

        movies = db.scalars(query).all()
        for movie in movies:
            if not needs_backdrop(movie):
                skipped += 1
                continue

            proposed_url = None
            source = None
            confidence = None
            error = ""
            tmdb_id = movie.tmdb_id

            if tmdb_id:
                try:
                    detail = _with_retries(
                        lambda: fetch_tmdb_detail(client, api_key, tmdb_id),
                        retries=args.retries,
                        backoff=args.backoff,
                    )
                    path = extract_image_path(detail)
                    proposed_url = build_backdrop_url(path)
                    source = "tmdb_id"
                except httpx.HTTPError as exc:
                    error = f"tmdb_id lookup failed: {exc.__class__.__name__}"
            else:
                try:
                    candidates = _with_retries(
                        lambda: movie_lookup.lookup_movie_candidates(
                            movie.title, movie.year, limit=5
                        ),
                        retries=args.retries,
                        backoff=args.backoff,
                    )
                except Exception as exc:
                    error = f"title search failed: {exc.__class__.__name__}"
                    candidates = []
                candidate = select_backdrop_candidate(
                    movie.title,
                    movie.year,
                    candidates,
                    args.min_confidence,
                )
                if candidate:
                    proposed_url = candidate.get("backdrop_url")
                    tmdb_id = candidate.get("tmdb_id") or tmdb_id
                    confidence = candidate.get("match_confidence")
                    source = "title_search"

            action = "skipped"
            if proposed_url:
                if args.apply and not args.dry_run:
                    movie.backdrop_url = proposed_url
                    if args.update_tmdb_id and not movie.tmdb_id and tmdb_id:
                        movie.tmdb_id = tmdb_id
                    db.add(movie)
                updated += 1
                action = "updated" if args.apply and not args.dry_run else "planned"

            results.append(
                {
                    "movie_id": movie.id,
                    "title": movie.title,
                    "year": movie.year,
                    "tmdb_id": movie.tmdb_id,
                    "imdb_id": movie.imdb_id,
                    "current_backdrop_url": movie.backdrop_url,
                    "proposed_backdrop_url": proposed_url or "",
                    "match_confidence": confidence or "",
                    "source": source or "",
                    "error": error,
                    "action": action,
                }
            )

            time.sleep(args.sleep)

        if args.apply and not args.dry_run:
            db.commit()

    write_report(report_path, results)
    print(f"report: {report_path}")
    print(f"updated: {updated}, skipped: {skipped}")
    if args.dry_run or not args.apply:
        print("dry run only: use --apply to write changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
