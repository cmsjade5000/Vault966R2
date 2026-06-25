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
from collections.abc import Mapping, Sequence as SequenceCollection
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: E402,F401  # ensure mapper registration
from api.utils.providers import split_providers  # noqa: E402


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
IMDB_ID_RE = re.compile(r"^tt\d{7,9}$", re.IGNORECASE)
ISO2_RE = re.compile(r"^[A-Za-z]{2}$")
YEAR_MIN = 1870
YEAR_MAX = 2100

# Contract: enriched_movies.csv must include these columns and pass validate_enriched_row.
ENRICHED_CSV_REQUIRED_COLUMNS = [
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
    "watch_region",
    "providers_stream",
    "providers_rent",
    "providers_buy",
    "tmdb_watch_url",
    "languages",
    "countries",
    "collection",
    "tmdb_last_scraped",
]

ENRICHED_CSV_V2_COLUMNS = [
    "languages_iso",
    "countries_iso",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich movie metadata from TMDb")
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "data" / "enriched_movies.csv"),
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
    parser.add_argument(
        "--v2",
        action="store_true",
        help="Emit normalized columns (providers_* + *_iso) alongside legacy columns.",
    )
    return parser.parse_args()


def _strip_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _is_valid_year(value: Any) -> bool:
    text = _strip_value(value)
    if not text:
        return False
    if not text.isdigit() or len(text) != 4:
        return False
    year = int(text)
    return YEAR_MIN <= year <= YEAR_MAX


def _is_valid_iso2(value: Any) -> bool:
    text = _strip_value(value)
    return bool(text and ISO2_RE.match(text))


def validate_enriched_row(row: Mapping[str, Any], *, movie_title: str) -> None:
    title = _strip_value(row.get("title"))
    if not title:
        raise ValueError(f"missing title for '{movie_title}'")

    year_raw = _strip_value(row.get("year"))
    imdb_id = _strip_value(row.get("imdb_id"))
    tmdb_id = _strip_value(row.get("tmdb_id"))
    if not year_raw and not imdb_id and not tmdb_id:
        raise ValueError(f"missing year/imdb_id/tmdb_id for '{movie_title}'")
    if year_raw and not _is_valid_year(year_raw):
        raise ValueError(f"invalid year '{year_raw}' for '{movie_title}'")
    if imdb_id and not IMDB_ID_RE.match(imdb_id):
        raise ValueError(f"invalid imdb_id '{imdb_id}' for '{movie_title}'")
    if tmdb_id and not tmdb_id.isdigit():
        raise ValueError(f"invalid tmdb_id '{tmdb_id}' for '{movie_title}'")

    watch_region = _strip_value(row.get("watch_region"))
    if watch_region and not _is_valid_iso2(watch_region):
        raise ValueError(f"invalid watch_region '{watch_region}' for '{movie_title}'")

    runtime_raw = _strip_value(row.get("runtime_min"))
    if runtime_raw and not runtime_raw.isdigit():
        raise ValueError(f"invalid runtime_min '{runtime_raw}' for '{movie_title}'")

    tmdb_last_scraped = _strip_value(row.get("tmdb_last_scraped"))
    if tmdb_last_scraped:
        try:
            datetime.fromisoformat(tmdb_last_scraped.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"invalid tmdb_last_scraped '{tmdb_last_scraped}' for '{movie_title}'"
            ) from exc


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


def _tokenize_string(value: str) -> List[str]:
    parts = re.split(r"[;,]", value)
    return [part.strip() for part in parts if part and part.strip()]


def _iter_existing_tokens(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        for token in _tokenize_string(value):
            yield token
        return
    if isinstance(value, Mapping):
        provider_name = value.get("provider_name")
        if provider_name is not None:
            yield from _iter_existing_tokens(provider_name)
            return
        for item in value.values():
            yield from _iter_existing_tokens(item)
        return
    if isinstance(value, SequenceCollection) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _iter_existing_tokens(item)
        return
    text = str(value).strip()
    if not text:
        return
    for token in _tokenize_string(text):
        yield token


def split_existing(value: Any) -> List[str]:
    tokens = list(_iter_existing_tokens(value))
    if not tokens:
        return []
    return split_providers(tokens)


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


def extract_provider_buckets(payload: Dict[str, object], region: str) -> Dict[str, object]:
    root = payload.get("watch/providers")
    if not isinstance(root, dict):
        return {"stream": [], "rent": [], "buy": [], "tmdb_watch_url": None}
    results = root.get("results")
    if not isinstance(results, dict):
        return {"stream": [], "rent": [], "buy": [], "tmdb_watch_url": None}
    region_data = results.get(region.upper()) or results.get("US") or {}
    if not isinstance(region_data, dict):
        return {"stream": [], "rent": [], "buy": [], "tmdb_watch_url": None}

    stream: List[str] = []
    rent: List[str] = []
    buy: List[str] = []

    for bucket in ("flatrate", "ads", "free"):
        entries = region_data.get(bucket) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("provider_name")
            if name:
                stream.append(str(name))

    for bucket, target in (("rent", rent), ("buy", buy)):
        entries = region_data.get(bucket) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("provider_name")
            if name:
                target.append(str(name))

    link = region_data.get("link")
    tmdb_watch_url = str(link).strip() if link else None
    return {
        "stream": split_providers(stream),
        "rent": split_providers(rent),
        "buy": split_providers(buy),
        "tmdb_watch_url": tmdb_watch_url,
    }


def extract_language_codes(payload: Dict[str, object], existing: Optional[str]) -> str:
    codes: List[str] = []
    spoken = payload.get("spoken_languages") or []
    if isinstance(spoken, list):
        for item in spoken:
            if isinstance(item, dict):
                code = item.get("iso_639_1")
                if code:
                    codes.append(str(code).lower())
    codes.extend([token.lower() for token in split_existing(existing) if len(token) == 2])
    return join_unique(codes)


def extract_country_codes(payload: Dict[str, object], existing: Optional[str]) -> str:
    codes: List[str] = []
    section = payload.get("production_countries") or []
    if isinstance(section, list):
        for item in section:
            if isinstance(item, dict):
                code = item.get("iso_3166_1")
                if code:
                    codes.append(str(code).upper())
    codes.extend([token.upper() for token in split_existing(existing) if len(token) == 2])
    return join_unique(codes)


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
    languages = movie.languages
    countries = movie.countries
    collection = movie.collection
    watch_region = provider_region.upper()
    providers_stream: List[str] = []
    providers_rent: List[str] = []
    providers_buy: List[str] = []
    tmdb_watch_url: Optional[str] = None

    def _populate_existing_provider_buckets(value: Any, region: str) -> None:
        nonlocal providers_stream, providers_rent, providers_buy
        if value is None:
            return
        if isinstance(value, dict):
            region_data = value.get(region.upper()) or value.get("US")
            if isinstance(region_data, dict):
                stream: List[str] = []
                rent: List[str] = []
                buy: List[str] = []
                for bucket in ("flatrate", "ads", "free"):
                    entries = region_data.get(bucket) or []
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        if isinstance(entry, dict) and entry.get("provider_name"):
                            stream.append(str(entry["provider_name"]))
                for bucket, target in (("rent", rent), ("buy", buy)):
                    entries = region_data.get(bucket) or []
                    if not isinstance(entries, list):
                        continue
                    for entry in entries:
                        if isinstance(entry, dict) and entry.get("provider_name"):
                            target.append(str(entry["provider_name"]))
                providers_stream = split_providers(stream)
                providers_rent = split_providers(rent)
                providers_buy = split_providers(buy)
                return

        # Fallback: treat any provider tokens as stream-only.
        providers_stream = split_existing(value)

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
        languages = extract_languages(payload, movie.languages)
        countries = extract_countries(payload, movie.countries)
        collection_data = payload.get("belongs_to_collection")
        if isinstance(collection_data, dict):
            name = collection_data.get("name")
            if name:
                collection = str(name)
        buckets = extract_provider_buckets(payload, provider_region)
        providers_stream = list(buckets.get("stream") or [])
        providers_rent = list(buckets.get("rent") or [])
        providers_buy = list(buckets.get("buy") or [])
        tmdb_watch_url = buckets.get("tmdb_watch_url") if isinstance(buckets, dict) else None
    else:
        _populate_existing_provider_buckets(movie.where_to_watch, provider_region)

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
        "watch_region": watch_region,
        "providers_stream": join_unique(providers_stream),
        "providers_rent": join_unique(providers_rent),
        "providers_buy": join_unique(providers_buy),
        "tmdb_watch_url": tmdb_watch_url or "",
        "languages": languages,
        "countries": countries,
        "collection": collection,
        "tmdb_last_scraped": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if payload:
        row["languages_iso"] = extract_language_codes(payload, movie.languages)
        row["countries_iso"] = extract_country_codes(payload, movie.countries)
    else:
        row["languages_iso"] = ""
        row["countries_iso"] = ""
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

    fieldnames = list(ENRICHED_CSV_REQUIRED_COLUMNS)
    if args.v2:
        fieldnames.extend(ENRICHED_CSV_V2_COLUMNS)

    mode = "a" if args.append else "w"
    processed = 0
    skipped_missing = 0
    failures = 0

    with output_path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
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
            try:
                validate_enriched_row(row, movie_title=movie.title)
            except ValueError as exc:
                logging.error("Enriched CSV contract violation: %s", exc)
                raise SystemExit(1) from exc
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
