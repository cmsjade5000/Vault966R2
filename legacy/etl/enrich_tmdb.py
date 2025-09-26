"""Fetch TMDb metadata for movies already stored in the database and emit a CSV.

This helper reads the current movie table, calls TMDb for each title that has a
`tmdb_id`, and writes an enriched CSV you can feed back into `etl_seed.py`.

The script is intentionally conservative:
- rows without a `tmdb_id` are skipped (logged to stderr)
- existing database values are kept when TMDb is missing data
- network hiccups are recorded and processing continues

Example:
    python scripts/enrich_tmdb.py --output data/enriched_movies.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import pathlib
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: E402,F401  # ensure mapper registration
from api.utils.providers import merge_providers  # noqa: E402


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich movie metadata from TMDb")
    parser.add_argument(
        "--output",
        default=str(ROOT_DIR / "data" / "enriched_movies.csv"),
        help="CSV path to write (default: data/enriched_movies.csv)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of movies to process",
    )
    parser.add_argument(
        "--country",
        default="US",
        help="Two-letter watch provider region code (default: US)",
    )
    parser.add_argument(
        "--poster-size",
        default="w500",
        help="Poster size segment for TMDb image URLs (default: w500)",
    )
    parser.add_argument(
        "--backdrop-size",
        default="w780",
        help="Backdrop size segment for TMDb image URLs (default: w780)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between TMDb requests (default: 0.25)",
    )
    parser.add_argument(
        "--allow-missing-tmdb",
        action="store_true",
        help="Emit rows even when tmdb_id is missing (uses DB values only)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the output file instead of overwriting",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def build_image_url(path: Optional[str], size: str) -> Optional[str]:
    if not path:
        return None
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{TMDB_IMAGE_BASE}/{size}{normalized}"


def join_unique(values: Iterable[Optional[str]]) -> str:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(text)
    return "; ".join(ordered)


def split_existing(value: Optional[str]) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[;,]", value)
    return [part.strip() for part in parts if part and part.strip()]


def extract_keywords(payload: Dict[str, object]) -> str:
    section = payload.get("keywords")
    candidates: Sequence[object]
    if isinstance(section, dict):
        candidates = section.get("keywords") or section.get("results") or []
    elif isinstance(section, list):
        candidates = section
    else:
        candidates = []

    names: List[str] = []
    for item in candidates:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(str(name))
        elif item:
            names.append(str(item))
    return join_unique(names)


def extract_providers(payload: Dict[str, object], region: str) -> str:
    root = payload.get("watch/providers")
    if not isinstance(root, dict):
        return ""
    results = root.get("results")
    if not isinstance(results, dict):
        return ""
    region_data = results.get(region.upper()) or results.get("US") or {}
    if not isinstance(region_data, dict):
        return ""

    providers: List[str] = []
    for bucket in ("flatrate", "ads", "free", "rent", "buy"):
        entries = region_data.get(bucket) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("provider_name")
            if not name:
                continue
            label = str(name)
            if bucket in {"rent", "buy"}:
                label = f"{label} ({bucket})"
            providers.append(label)
    return join_unique(providers)


def extract_languages(payload: Dict[str, object], existing: Optional[str]) -> str:
    languages = []
    spoken = payload.get("spoken_languages") or []
    if isinstance(spoken, list):
        for item in spoken:
            if isinstance(item, dict):
                label = item.get("english_name") or item.get("name")
                if label:
                    languages.append(str(label))
    languages.extend(split_existing(existing))
    return join_unique(languages)


def extract_countries(payload: Dict[str, object], existing: Optional[str]) -> str:
    countries = []
    section = payload.get("production_countries") or []
    if isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                label = item.get("english_name") or item.get("name") or item.get("iso_3166_1")
                if label:
                    countries.append(str(label))
    countries.extend(split_existing(existing))
    return join_unique(countries)


def extract_genres(payload: Dict[str, object], existing: Sequence[str]) -> str:
    tmdb_genres = []
    section = payload.get("genres") or []
    if isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    tmdb_genres.append(str(name))
    return join_unique([*tmdb_genres, *existing])


def extract_plot(payload: Dict[str, object], fallback: Optional[str]) -> Optional[str]:
    overview = payload.get("overview")
    text = str(overview).strip() if overview else ""
    if text:
        return text
    return fallback


def fetch_tmdb_payload(
    client: httpx.Client, api_key: str, tmdb_id: int
) -> Optional[Dict[str, object]]:
    try:
        response = client.get(
            f"/movie/{tmdb_id}",
            params={
                "api_key": api_key,
                "append_to_response": "keywords,watch/providers",
            },
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logging.warning("TMDb %s failed (%s)", tmdb_id, exc.response.status_code)
        return None
    except httpx.HTTPError as exc:
        logging.warning("TMDb %s error: %s", tmdb_id, exc)
        return None

    if not isinstance(data, dict):
        logging.warning("TMDb %s returned unexpected payload", tmdb_id)
        return None
    return data


def build_row(
    movie: Movie,
    payload: Optional[Dict[str, object]],
    *,
    poster_size: str,
    backdrop_size: str,
    provider_region: str,
) -> Dict[str, Optional[str]]:
    existing_genres = [genre.name for genre in getattr(movie, "genres", []) if genre.name]
    existing_moods = [mood.name for mood in getattr(movie, "moods", []) if mood.name]

    poster_url: Optional[str] = movie.poster_url
    backdrop_url: Optional[str] = movie.backdrop_url
    runtime_min: Optional[int] = movie.runtime
    plot = movie.plot
    genres = join_unique(existing_genres)
    moods = join_unique(existing_moods)
    keywords = ""
    provider_tokens = split_existing(movie.where_to_watch)
    languages = movie.languages
    countries = movie.countries
    collection = movie.collection

    if payload:
        poster_candidate = build_image_url(payload.get("poster_path"), poster_size)
        backdrop_candidate = build_image_url(payload.get("backdrop_path"), backdrop_size)
        if poster_candidate:
            poster_url = poster_candidate
        if backdrop_candidate:
            backdrop_url = backdrop_candidate

        runtime_val = payload.get("runtime")
        if isinstance(runtime_val, int):
            runtime_min = runtime_val

        plot = extract_plot(payload, plot)
        genres = extract_genres(payload, existing_genres)
        moods = join_unique(existing_moods)  # TMDb does not provide moods
        keywords = extract_keywords(payload)
        provider_string = extract_providers(payload, provider_region)
        if provider_string:
            provider_tokens = merge_providers(provider_tokens, split_existing(provider_string))
        languages = extract_languages(payload, movie.languages)
        countries = extract_countries(payload, movie.countries)
        collection_data = payload.get("belongs_to_collection")
        if isinstance(collection_data, dict):
            name = collection_data.get("name")
            if name:
                collection = str(name)

    row = {
        "title": movie.title,
        "year": movie.year,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "runtime_min": runtime_min,
        "plot": plot,
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "genres": genres,
        "moods": moods,
        "keywords": keywords,
        "imdb_rating": movie.imdb_rating,
        "imdb_votes": movie.imdb_votes,
        "rt_score": movie.rt_score,
        "where_to_watch": "; ".join(provider_tokens) if provider_tokens else "",
        "languages": languages,
        "countries": countries,
        "collection": collection,
        "tmdb_last_scraped": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return row


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        logging.error("TMDB_API_KEY is not set in the environment")
        return 2

    output_path = pathlib.Path(args.output)
    if output_path.exists() and not args.append:
        logging.info("Removing existing output at %s", output_path)
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        stmt = (
            select(Movie)
            .options(selectinload(Movie.genres), selectinload(Movie.moods))
            .order_by(Movie.title)
        )
        if not args.allow_missing_tmdb:
            stmt = stmt.where(Movie.tmdb_id.isnot(None))
        if args.limit:
            stmt = stmt.limit(args.limit)
        movies = list(session.execute(stmt).scalars())

    total = len(movies)
    if total == 0:
        logging.warning("No movies found to process")
        return 0

    logging.info("Processing %s movies", total)

    client = httpx.Client(
        base_url=TMDB_API_BASE,
        timeout=15.0,
        headers={"Accept": "application/json"},
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=5),
    )

    fieldnames = [
        "title",
        "year",
        "imdb_id",
        "tmdb_id",
        "runtime_min",
        "plot",
        "poster_url",
        "backdrop_url",
        "genres",
        "moods",
        "keywords",
        "imdb_rating",
        "imdb_votes",
        "rt_score",
        "where_to_watch",
        "languages",
        "countries",
        "collection",
        "tmdb_last_scraped",
    ]

    mode = "a" if args.append else "w"
    processed = 0
    skipped_missing = 0
    failures = 0

    with output_path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not args.append or handle.tell() == 0:
            writer.writeheader()

        for movie in movies:
            if not movie.tmdb_id and not args.allow_missing_tmdb:
                skipped_missing += 1
                logging.debug("Skipping %s (no tmdb_id)", movie.title)
                continue

            payload = None
            if movie.tmdb_id:
                payload = fetch_tmdb_payload(client, api_key, movie.tmdb_id)
                if payload is None:
                    failures += 1
            row = build_row(
                movie,
                payload,
                poster_size=args.poster_size,
                backdrop_size=args.backdrop_size,
                provider_region=args.country,
            )
            writer.writerow(row)
            processed += 1

            if args.sleep:
                time.sleep(args.sleep)

    client.close()

    logging.info(
        "Completed. rows=%s skipped_no_tmdb=%s tmdb_failures=%s -> %s",
        processed,
        skipped_missing,
        failures,
        output_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
