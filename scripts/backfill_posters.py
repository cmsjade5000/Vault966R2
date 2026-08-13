"""Backfill missing poster URLs in the database using TMDb/OMDb.

Related skill: `poster-backdrop-audit`.

Requires TMDB_API_KEY (preferred) and/or OMDB_API_KEY in the environment
or via --tmdb-key/--omdb-key.

Dry run:
  python scripts/backfill_posters.py --dry-run

Apply updates and write a report:
  python scripts/backfill_posters.py --report reports/poster_backfill.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import pathlib
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config import settings  # noqa: E402
from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.movie_flag import MovieFlag  # noqa: E402
from api.models.person import Role  # noqa: E402,F401  # ensure mapper registration
from api.services import movie_lookup  # noqa: E402
from api.services.movie_review import get_review_queue  # noqa: E402
from api.services.source_sync import get_source_review_queue  # noqa: E402
from api.utils.provider_errors import run_provider_cli  # noqa: E402
from scripts.backfill_db_backup import backup_active_sqlite_database  # noqa: E402

TMDB_IMAGE_HOSTS = {"image.tmdb.org", "media.themoviedb.org"}
TMDB_IMAGE_PATH_RE = re.compile(r"^/t/p/(?:original|w\d+)/[^/]+\.(?:jpe?g|png|webp)$", re.I)


class _OpenGraphImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[str] = []
        self.titles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "meta":
            return
        values = {key.casefold(): value for key, value in attrs if value is not None}
        property_name = values.get("property", "").casefold()
        if property_name == "og:image" and values.get("content"):
            self.images.append(values["content"])
        elif property_name == "og:title" and values.get("content"):
            self.titles.append(values["content"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing movie poster URLs")
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
        "--omdb-key",
        default=None,
        help="OMDb API key (default: env OMDB_API_KEY).",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT_DIR / "reports" / "poster_backfill.csv"),
        help="CSV report output path (default: reports/poster_backfill.csv).",
    )
    parser.add_argument(
        "--update-tmdb-id",
        action="store_true",
        help="Populate tmdb_id when missing and the match confidence meets the threshold.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log changes without writing to the database.",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Include movies in source review, Vault checks, or the manual flag queue.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Concurrent workers for keyless TMDB page reads (default: 4, maximum: 8).",
    )
    return parser.parse_args()


def normalize_title(title: str) -> str:
    cleaned = title.strip().lower()
    cleaned = cleaned.replace("&", "and")
    suffix_pattern = re.compile(
        r"(?:"
        r"\s*[\[(](?:18|19|20)\d{2}[\])]"
        r"|\s*\((?:unrated|uncut(?: version)?|newly remastered|"
        r"extended(?: edition| cut)?|unrated extended edition|"
        r"director'?s (?:cut|definitive cut)|new extended cut|"
        r"special edition|theatrical cut|final cut|restored edition|"
        r"the ultimate edition|the magnum edition)\)"
        r")\s*$",
        flags=re.I,
    )
    previous = None
    while cleaned != previous:
        previous = cleaned
        cleaned = suffix_pattern.sub("", cleaned)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
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


def select_poster_candidate(
    requested_title: str,
    requested_year: Optional[int],
    candidates: Iterable[Dict[str, Any]],
    min_confidence: float,
) -> Optional[Dict[str, Any]]:
    scored: list[tuple[Dict[str, Any], float, bool, int, int]] = []
    for candidate in candidates:
        poster_url = candidate.get("poster_url")
        if not poster_url:
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


def build_image_url(path: Optional[str], size: str) -> Optional[str]:
    if not path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{path}"


def extract_image_path(
    detail: Dict[str, Any], primary_key: str, fallback_key: str
) -> Optional[str]:
    path = detail.get(primary_key)
    if path:
        return path
    images = detail.get("images")
    if not isinstance(images, dict):
        return None
    items = images.get(fallback_key) or []
    if not isinstance(items, list):
        return None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        file_path = entry.get("file_path")
        if file_path:
            return file_path
    return None


def fetch_tmdb_detail(client: httpx.Client, api_key: str, tmdb_id: int) -> Dict[str, Any]:
    params = {
        "api_key": api_key,
        "append_to_response": "images,release_dates",
    }
    response = client.get(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}",
        params=params,
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def valid_tmdb_poster_url(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "https"
        or parsed.hostname not in TMDB_IMAGE_HOSTS
        or not TMDB_IMAGE_PATH_RE.fullmatch(parsed.path)
    ):
        return None
    return value.strip()


def fetch_tmdb_page_match(client: httpx.Client, tmdb_id: int) -> Dict[str, Optional[str]]:
    response = client.get(
        f"https://www.themoviedb.org/movie/{tmdb_id}",
        headers={"User-Agent": "Vault966/1.0"},
        follow_redirects=True,
        timeout=15.0,
    )
    response.raise_for_status()
    parser = _OpenGraphImageParser()
    parser.feed(response.text)
    title = parser.titles[0].strip() if parser.titles else None
    for image in parser.images:
        poster_url = valid_tmdb_poster_url(image)
        if poster_url:
            return {"title": title, "poster_url": poster_url}
    return {"title": title, "poster_url": None}


def fetch_tmdb_page_poster(client: httpx.Client, tmdb_id: int) -> Optional[str]:
    return fetch_tmdb_page_match(client, tmdb_id)["poster_url"]


def fetch_tmdb_page_match_isolated(tmdb_id: int) -> Dict[str, Optional[str]]:
    with httpx.Client() as client:
        return fetch_tmdb_page_match(client, tmdb_id)


def fetch_omdb_detail(client: httpx.Client, api_key: str, imdb_id: str) -> Optional[Dict[str, Any]]:
    response = client.get(
        "https://www.omdbapi.com/",
        params={"apikey": api_key, "i": imdb_id},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload or str(payload.get("Response")) != "True":
        return None
    return payload


def needs_poster(movie: Movie) -> bool:
    poster = (movie.poster_url or "").strip()
    return not poster


def write_report(path: pathlib.Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    tmdb_key = args.tmdb_key or settings.tmdb_api_key or os.getenv("TMDB_API_KEY")
    omdb_key = args.omdb_key or settings.omdb_api_key or os.getenv("OMDB_API_KEY")

    now = datetime.now(timezone.utc)
    report_rows: list[Dict[str, Any]] = []
    attempted = 0
    updated = 0

    if not args.dry_run:
        backup = backup_active_sqlite_database("poster backfill", now=now)
        print(f"backup: {backup.backup}")

    with SessionLocal() as session, httpx.Client() as client:
        movies = session.execute(select(Movie).order_by(Movie.id)).scalars().all()
        excluded_movie_ids: set[int] = set()
        if not args.include_review:
            excluded_movie_ids.update(
                item.movie.id for item in get_source_review_queue(session) if item.movie
            )
            excluded_movie_ids.update(item.movie.id for item in get_review_queue(session)[0])
            excluded_movie_ids.update(session.execute(select(MovieFlag.movie_id)).scalars().all())
        missing = [
            movie for movie in movies if needs_poster(movie) and movie.id not in excluded_movie_ids
        ]
        if args.limit:
            missing = missing[: args.limit]

        page_matches: dict[int, Dict[str, Optional[str]]] = {}
        if not tmdb_key:
            page_candidates = [movie for movie in missing if movie.tmdb_id]
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {
                    executor.submit(fetch_tmdb_page_match_isolated, movie.tmdb_id): movie.id
                    for movie in page_candidates
                }
                for future in as_completed(futures):
                    movie_id = futures[future]
                    try:
                        page_matches[movie_id] = future.result()
                    except httpx.HTTPError:
                        page_matches[movie_id] = {"title": None, "poster_url": None}

        for movie in missing:
            attempted += 1

            match_source = "tmdb_search"
            candidate = None
            poster_url = None
            matched_tmdb_id = None
            matched_title = None
            matched_year = None
            match_strategy = None
            match_confidence = None

            if movie.tmdb_id and tmdb_key:
                match_source = "tmdb_id"
                detail = fetch_tmdb_detail(client, tmdb_key, movie.tmdb_id)
                poster_path = extract_image_path(detail, "poster_path", "posters")
                poster_url = build_image_url(poster_path, "w342")
                matched_tmdb_id = movie.tmdb_id
                matched_title = detail.get("title") or detail.get("name") or movie.title
                matched_year = movie.year
                match_strategy = "tmdb_id"
                match_confidence = 1.0
            elif movie.tmdb_id:
                match_source = "tmdb_page_id"
                page_match = page_matches.get(movie.id) or {}
                matched_tmdb_id = movie.tmdb_id
                matched_title = page_match.get("title")
                matched_year = movie.year
                match_strategy = "tmdb_page_id"
                title_matches = bool(
                    matched_title and normalize_title(matched_title) == normalize_title(movie.title)
                )
                match_confidence = 1.0 if title_matches else 0.0
                if title_matches:
                    poster_url = page_match.get("poster_url")
            elif tmdb_key:
                match_source = "tmdb_search"
                try:
                    candidates = movie_lookup.lookup_movie_candidates(
                        movie.title,
                        movie.year,
                        limit=5,
                    )
                except movie_lookup.MovieLookupError:
                    candidates = []
                except movie_lookup.MovieLookupUnavailable:
                    candidates = []
                candidate = select_poster_candidate(
                    movie.title,
                    movie.year,
                    candidates,
                    args.min_confidence,
                )
                if candidate:
                    poster_url = candidate.get("poster_url")
                    matched_tmdb_id = candidate.get("tmdb_id")
                    matched_title = candidate.get("matched_tmdb_title") or candidate.get("title")
                    matched_year = candidate.get("matched_tmdb_year") or candidate.get("year")
                    match_strategy = candidate.get("match_strategy")
                    match_confidence = candidate.get("match_confidence")
                    if (
                        args.update_tmdb_id
                        and not args.dry_run
                        and not movie.tmdb_id
                        and matched_tmdb_id
                    ):
                        movie.tmdb_id = int(matched_tmdb_id)
            elif omdb_key and movie.imdb_id:
                match_source = "omdb"
                payload = fetch_omdb_detail(client, omdb_key, movie.imdb_id)
                if payload:
                    poster = payload.get("Poster")
                    if poster and poster != "N/A":
                        poster_url = poster
            else:
                match_source = "none"

            if poster_url:
                if not args.dry_run:
                    movie.poster_url = poster_url
                    if match_source.startswith("tmdb"):
                        movie.last_tmdb_fetch_at = now
                    elif match_source == "omdb":
                        movie.last_omdb_fetch_at = now
                updated += 1

            report_rows.append(
                {
                    "movie_id": movie.id,
                    "vault_id": movie.vault_id or "",
                    "title": movie.title,
                    "year": movie.year or "",
                    "imdb_id": movie.imdb_id or "",
                    "tmdb_id": movie.tmdb_id or "",
                    "matched_tmdb_id": matched_tmdb_id or "",
                    "matched_title": matched_title or "",
                    "matched_year": matched_year or "",
                    "match_strategy": match_strategy or "",
                    "match_confidence": match_confidence or "",
                    "poster_url": poster_url or "",
                    "source": match_source,
                    "status": "updated" if poster_url else "missing",
                }
            )

            if args.sleep:
                time.sleep(args.sleep)

        if not args.dry_run:
            session.commit()

    report_path = pathlib.Path(args.report)
    write_report(report_path, report_rows)

    print(
        "Poster backfill complete. "
        f"attempted={attempted} updated={updated} "
        f"report={report_path if report_rows else 'n/a'} "
        f"dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_provider_cli(main))
