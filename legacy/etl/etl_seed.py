"""Flexible importer for loading movie metadata into the database.

Features:
- Supports JSON or CSV input via --path/--format (format inferred from extension when omitted).
- Deduplicates movies based on imdb_id, updating existing records when found.
- Upserts genres and moods by name for every row.
- Provides a --dry-run flag to simulate the import without committing changes.
- Logs a concise summary (inserted/updated/skipped with reasons); malformed rows generate
  errors and force a non-zero exit code, while recoverable issues continue processing.

Usage examples:
    python scripts/etl_seed.py --path scripts/samples/sample_movies.json --format json
    python scripts/etl_seed.py --path bulk_movies.csv --format csv --dry-run
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import pathlib
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from api.db import Base, SessionLocal, engine
from api.models.movie import Genre, Mood, Movie, MovieIngestProvenance
from api.models.person import Role  # noqa: F401 - ensure mapper registration
from api.utils.providers import merge_providers

logger = logging.getLogger(__name__)


class MalformedRowError(Exception):
    """Row is malformed and should fail the import run."""


class RecoverableRowError(Exception):
    """Row failed but the overall import may proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import movies into the database")
    parser.add_argument("--path", required=True, help="Path to the input file (JSON or CSV)")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Input format. If omitted, inferred from the file extension.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run import without committing any changes.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Disable network lookups for missing imdb_id",
    )
    parser.add_argument(
        "--allow-tmdb-only",
        action="store_true",
        help="Allow inserts using tmdb_id when imdb_id cannot be resolved",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    return parser.parse_args()


def infer_format(path: pathlib.Path, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "csv"
    raise ValueError("Could not infer format; please provide --format explicitly")


def _normalize_column_name(value: str) -> str:
    cleaned = value.replace("\ufeff", "").strip()
    cleaned = cleaned.strip("\"'`")
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    return cleaned.lower()


def _find_csv_header_index(lines: List[str]) -> int:
    for index, raw_line in enumerate(lines):
        if not raw_line.strip():
            continue
        parsed = next(csv.reader([raw_line]))
        normalized = [_normalize_column_name(part) for part in parsed if part is not None]
        if not normalized:
            continue
        if any("title" in name and "subtitle" not in name for name in normalized):
            return index
    raise MalformedRowError("CSV file is missing a header row containing a title column")


def load_rows(path: pathlib.Path, file_format: str, encoding: str) -> List[Dict[str, Any]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        if file_format == "json":
            raw = json.load(handle)
            if not isinstance(raw, list):
                raise MalformedRowError("JSON payload must be a list of objects")
            return [dict(row) for row in raw]

        lines = list(handle)
        if not lines:
            return []

        header_index = _find_csv_header_index(lines)
        csv_lines = lines[header_index:]
        if not csv_lines:
            return []

        csv_lines[0] = csv_lines[0].lstrip("\ufeff")
        reader = csv.DictReader(csv_lines)

        rows: List[Dict[str, Any]] = []
        for row in reader:
            cleaned = {key: value for key, value in row.items() if key is not None}
            rows.append(cleaned)
        return rows


_NULL_STRINGS = {"", " ", "n/a", "N/A", "unknown", "NULL", "NaN", "nan", None}

resolver_state = SimpleNamespace(last_tmdb_imdb_id=None, last_omdb_payload=None)


def normalize_title(title: str) -> str:
    import re

    replacements = {
        "&": "and",
    }
    normalized = title.lower().strip()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def sanitize_title_for_search(title: str) -> str:
    import re

    # Strip parenthetical descriptors such as "(2020)", "(Unrated)", etc., so search
    # queries focus on the canonical title text.
    without_parentheticals = re.sub(r"\s*\([^)]*\)\s*", " ", title)
    sanitized = normalize_title(without_parentheticals)
    if sanitized:
        return sanitized
    # Fall back to a normalized version of the original title to avoid empty
    # queries when the input is entirely punctuation or whitespace.
    fallback = normalize_title(title)
    return fallback if fallback else title.strip().lower()


def extract_imdb_from_tmdb_external_ids(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not data:
        return None
    return normalize_imdb_id(data.get("imdb_id"))


def extract_imdb_from_omdb(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not data:
        return None
    response_flag = str(data.get("Response", "")).lower()
    if response_flag != "true":
        return None
    return normalize_imdb_id(data.get("imdbID"))


def pick_imdb_id(
    tmdb_json: Optional[Dict[str, Any]], omdb_json: Optional[Dict[str, Any]]
) -> Optional[str]:
    return extract_imdb_from_tmdb_external_ids(tmdb_json) or extract_imdb_from_omdb(omdb_json)


def load_overrides(path: pathlib.Path) -> Dict[Tuple[str, Optional[int]], str]:
    overrides: Dict[Tuple[str, Optional[int]], str] = {}
    if not path.exists():
        return overrides

    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_title = row.get("title")
            raw_year = row.get("year")
            raw_imdb = row.get("imdb_id")
            if not raw_title or not raw_imdb:
                continue
            normalized = normalize_imdb_id(raw_imdb)
            if not normalized:
                continue
            title_key = raw_title.strip().lower()
            year_key = coerce_int(raw_year)
            overrides[(title_key, year_key)] = normalized
            overrides[(title_key, None)] = normalized
    return overrides


def coerce_int(
    value: Any, *, min_value: Optional[int] = None, max_value: Optional[int] = None
) -> Optional[int]:
    if value in _NULL_STRINGS:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        result = value
    else:
        text = str(value).strip()
        if not text or text in _NULL_STRINGS:
            return None
        try:
            if "." in text:
                result = int(float(text))
            else:
                result = int(text)
        except ValueError:
            return None

    if min_value is not None and result < min_value:
        return None
    if max_value is not None and result > max_value:
        return None
    return result


def split_multi(value: Any) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        candidates = value
    else:
        candidates = [part.strip() for part in str(value).replace(";", ",").split(",")]

    seen = set()
    result: List[str] = []
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _first_value(mapping: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in mapping:
            value = mapping[key]
            if value not in (None, ""):
                return value
    return None


def normalize_imdb_id(value: Any) -> Optional[str]:
    if value in _NULL_STRINGS:
        return None
    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    if lowered.startswith("tt"):
        digits = lowered[2:]
    elif lowered.isdigit():
        digits = lowered
    else:
        stripped = lowered.replace("tt", "")
        if stripped.isdigit():
            digits = stripped
        else:
            return None

    if not digits or not digits.isdigit():
        return None

    length = len(digits)
    if length < 7 or length > 9:
        return None

    return f"tt{digits.zfill(7)}"


def coerce_float(
    value: Any, *, min_value: Optional[float] = None, max_value: Optional[float] = None
) -> Optional[float]:
    if value in _NULL_STRINGS:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = str(value).strip().lower()
        if not text or text in _NULL_STRINGS:
            return None
        text = text.replace(",", ".")
        try:
            result = float(text)
        except ValueError:
            return None

    if min_value is not None and result < min_value:
        return None
    if max_value is not None and result > max_value:
        return None
    return result


def clean_text(value: Any) -> Optional[str]:
    if value in _NULL_STRINGS:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_providers(value: Any) -> List[str]:
    if value in _NULL_STRINGS or value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        tokens: List[str] = []
        for item in value:
            tokens.extend(_split_providers(item))
        return tokens
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[;,]", text)
    return [part.strip() for part in parts if part.strip()]


def normalize_providers(value: Any) -> Optional[str]:
    providers = merge_providers(_split_providers(value))
    return "; ".join(providers) if providers else None


def merge_where_to_watch(existing_value: Any, new_value: Any) -> Optional[str]:
    providers = merge_providers(_split_providers(existing_value), _split_providers(new_value))
    return "; ".join(providers) if providers else None


def normalize_row(raw: Dict[str, Any], row_number: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise MalformedRowError(f"Row {row_number}: expected an object, got {type(raw).__name__}")

    title_raw = raw.get("title")
    title = str(title_raw).strip() if title_raw is not None else ""
    if not title:
        raise MalformedRowError(f"Row {row_number}: missing required field 'title'")

    imdb_id_raw = _first_value(raw, ["imdb_id"])
    imdb_id = normalize_imdb_id(imdb_id_raw)
    imdb_invalid = bool(imdb_id_raw not in (None, "")) and imdb_id is None

    year_value = _first_value(raw, ["year", "release_year", "verified_year"])
    runtime_value = _first_value(raw, ["runtime", "runtime_min", "minutes"])
    plot_value = _first_value(raw, ["plot", "plot_summary", "overview"])
    tmdb_value = _first_value(raw, ["tmdb_id"])
    poster_value = _first_value(raw, ["poster_url"])
    backdrop_value = _first_value(raw, ["backdrop_url"])
    genres_value = _first_value(raw, ["genre", "genres"])
    moods_value = _first_value(raw, ["mood", "moods"])
    imdb_rating_value = _first_value(raw, ["imdb_rating"])
    imdb_votes_value = _first_value(raw, ["imdb_votes"])
    rt_score_value = _first_value(raw, ["rt_score", "rt_percent"])
    where_value = _first_value(raw, ["where_to_watch", "digital_location"])
    languages_value = _first_value(raw, ["languages"])
    countries_value = _first_value(raw, ["countries"])
    collection_value = _first_value(raw, ["collection", "franchise"])

    record = {
        "title": title,
        "year": coerce_int(year_value, min_value=1870, max_value=2100),
        "runtime": coerce_int(runtime_value, min_value=1, max_value=1000),
        "plot": clean_text(plot_value),
        "imdb_id": imdb_id,
        "imdb_id_original": imdb_id_raw,
        "imdb_invalid": imdb_invalid,
        "tmdb_id": coerce_int(tmdb_value, min_value=1),
        "poster_url": clean_text(poster_value),
        "backdrop_url": clean_text(backdrop_value),
        "genres": split_multi(genres_value),
        "moods": split_multi(moods_value),
        "imdb_rating": coerce_float(imdb_rating_value, min_value=0.0, max_value=10.0),
        "imdb_votes": coerce_int(imdb_votes_value, min_value=0),
        "rt_score": coerce_int(rt_score_value, min_value=0, max_value=100),
        "where_to_watch": normalize_providers(where_value),
        "languages": clean_text(languages_value),
        "countries": clean_text(countries_value),
        "collection": clean_text(collection_value),
    }
    return record


def get_or_create_genre(session, name: str) -> Genre:
    stmt = select(Genre).where(Genre.name == name)
    genre = session.execute(stmt).scalar_one_or_none()
    if genre is None:
        genre = Genre(name=name)
        session.add(genre)
    return genre


def get_or_create_mood(session, name: str) -> Mood:
    stmt = select(Mood).where(Mood.name == name)
    mood = session.execute(stmt).scalar_one_or_none()
    if mood is None:
        mood = Mood(name=name)
        session.add(mood)
    return mood


class Summary:
    def __init__(self) -> None:
        self.inserted = 0
        self.updated = 0
        self.skipped = 0
        self.skip_reasons: Dict[str, int] = defaultdict(int)
        self.malformed: List[str] = []

    def record_skip(self, reason: str) -> None:
        self.skipped += 1
        self.skip_reasons[reason] += 1

    def record_malformed(self, message: str) -> None:
        self.malformed.append(message)
        self.record_skip("malformed")

    def log(self, dry_run: bool) -> None:
        logger.info(
            "Import summary (dry_run=%s): inserted=%s, updated=%s, skipped=%s",
            dry_run,
            self.inserted,
            self.updated,
            self.skipped,
        )

        if self.skip_reasons:
            logger.info("Top skip reasons:")
            for reason, count in Counter(self.skip_reasons).most_common(5):
                logger.info("  %s: %s", reason, count)
        else:
            logger.info("No skipped rows recorded.")
        if self.malformed:
            logger.error("Malformed rows detected (%s):", len(self.malformed))
            for message in self.malformed:
                logger.error("  %s", message)
        else:
            logger.info("No malformed rows encountered.")


def _has_changes(existing: Movie, record: Dict[str, Any]) -> bool:
    if (
        existing.title != record["title"]
        or existing.year != record["year"]
        or existing.runtime != record["runtime"]
        or existing.plot != record["plot"]
        or existing.tmdb_id != record["tmdb_id"]
        or existing.imdb_rating != record.get("imdb_rating")
        or existing.imdb_votes != record.get("imdb_votes")
        or existing.rt_score != record.get("rt_score")
        or existing.where_to_watch != record.get("where_to_watch")
        or existing.languages != record.get("languages")
        or existing.countries != record.get("countries")
        or existing.collection != record.get("collection")
        or existing.poster_url != record["poster_url"]
        or existing.backdrop_url != record["backdrop_url"]
    ):
        return True

    current_genres = {genre.name for genre in existing.genres}
    current_moods = {mood.name for mood in existing.moods}
    return current_genres != set(record["genres"]) or current_moods != set(record["moods"])


def _merge_values(existing_value: Optional[Any], new_value: Optional[Any]) -> Optional[Any]:
    if new_value in _NULL_STRINGS or new_value is None:
        return existing_value
    return new_value


def _merge_lists(existing_items, new_items):
    if not new_items:
        return existing_items
    return new_items


def _write_db_duplicate(row: Dict[str, Any], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                row.get("title"),
                row.get("imdb_id_original"),
                row.get("imdb_id"),
                row.get("tmdb_id"),
            ]
        )


def _normalize_snapshot_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "title": payload.get("title"),
        "year": payload.get("year"),
        "runtime": payload.get("runtime"),
        "plot": payload.get("plot"),
        "imdb_id": payload.get("imdb_id"),
        "tmdb_id": payload.get("tmdb_id"),
        "imdb_rating": payload.get("imdb_rating"),
        "imdb_votes": payload.get("imdb_votes"),
        "rt_score": payload.get("rt_score"),
        "where_to_watch": payload.get("where_to_watch"),
        "languages": payload.get("languages"),
        "countries": payload.get("countries"),
        "collection": payload.get("collection"),
        "poster_url": payload.get("poster_url"),
        "backdrop_url": payload.get("backdrop_url"),
        "genres": sorted(payload.get("genres", [])),
        "moods": sorted(payload.get("moods", [])),
    }
    return normalized


def build_record_signature(record: Dict[str, Any]) -> tuple[str, str]:
    normalized = _normalize_snapshot_payload(record)
    payload_json = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return payload_json, payload_hash


def build_movie_signature(movie: Movie) -> tuple[str, str]:
    payload = {
        "title": movie.title,
        "year": movie.year,
        "runtime": movie.runtime,
        "plot": movie.plot,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "imdb_rating": movie.imdb_rating,
        "imdb_votes": movie.imdb_votes,
        "rt_score": movie.rt_score,
        "where_to_watch": movie.where_to_watch,
        "languages": movie.languages,
        "countries": movie.countries,
        "collection": movie.collection,
        "poster_url": movie.poster_url,
        "backdrop_url": movie.backdrop_url,
        "genres": [genre.name for genre in movie.genres],
        "moods": [mood.name for mood in movie.moods],
    }
    normalized = _normalize_snapshot_payload(payload)
    payload_json = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return payload_json, payload_hash


def apply_overrides(
    record: Dict[str, Any],
    overrides: Dict[Tuple[str, Optional[int]], str],
    row_number: int,
    log_path: pathlib.Path,
) -> Optional[str]:
    title_key = record["title"].strip().lower()
    year = record.get("year")
    imdb_id = overrides.get((title_key, year)) or overrides.get((title_key, None))
    if imdb_id:
        record["imdb_id"] = imdb_id
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([row_number, record["title"], year, imdb_id])
    return imdb_id


def resolve_imdb_via_network(
    record: Dict[str, Any],
    *,
    allow_network: bool,
    tmdb_key: Optional[str],
    omdb_key: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    resolver_state.last_tmdb_imdb_id = None
    resolver_state.last_omdb_payload = None

    if not allow_network:
        return None, "network_disabled", None

    title = record["title"]
    year = record.get("year")
    sanitized_title = sanitize_title_for_search(title)
    omdb_title = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
    omdb_title = re.sub(r"\s{2,}", " ", omdb_title)
    if not omdb_title:
        omdb_title = title.strip()

    if not tmdb_key and not omdb_key:
        return None, "api_keys_missing", None

    tmdb_candidate: Optional[int] = None

    if tmdb_key:
        try:
            params = {"query": sanitized_title, "api_key": tmdb_key}
            if year:
                params["year"] = year
            response = httpx.get(
                "https://api.themoviedb.org/3/search/movie", params=params, timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            for result in results:
                result_title = str(result.get("title", ""))
                if sanitize_title_for_search(result_title) != sanitized_title:
                    continue
                release_date = result.get("release_date") or ""
                release_year = int(release_date[:4]) if release_date[:4].isdigit() else None
                if year and release_year and abs(release_year - year) > 1:
                    continue
                tmdb_id = result.get("id")
                if tmdb_id:
                    tmdb_candidate = tmdb_id
                    external = httpx.get(
                        f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids",
                        params={"api_key": tmdb_key},
                        timeout=10.0,
                    )
                    external.raise_for_status()
                    external_payload = external.json()
                    imdb_id = extract_imdb_from_tmdb_external_ids(external_payload)
                    if imdb_id:
                        resolver_state.last_tmdb_imdb_id = imdb_id
                        return imdb_id, "tmdb", tmdb_id
                    resolver_state.last_tmdb_imdb_id = extract_imdb_from_tmdb_external_ids(
                        external_payload
                    )
        except httpx.HTTPError as exc:
            logger.warning("TMDb lookup failed: %s", exc)

    def _omdb_lookup(params: Dict[str, Any], tag: str) -> Optional[Tuple[str, str, Optional[int]]]:
        # Use a copy so we can mutate for logging/testing without affecting callers.
        query_params = dict(params)
        try:
            response = httpx.get("https://www.omdbapi.com/", params=query_params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            resolver_state.last_omdb_payload = data
            imdb_id = extract_imdb_from_omdb(data)
            if not imdb_id:
                return None
            if year:
                omdb_year = data.get("Year")
                try:
                    omdb_year_int = int(str(omdb_year).split("–")[0]) if omdb_year else None
                except ValueError:
                    omdb_year_int = None
                if omdb_year_int is not None and abs(omdb_year_int - year) > 1:
                    return None
            return imdb_id, tag, tmdb_candidate
        except httpx.HTTPError as exc:
            logger.warning("OMDb lookup failed: %s", exc)
            return None

    if omdb_key:
        query_title = omdb_title or title
        if year:
            result = _omdb_lookup(
                {"apikey": omdb_key, "t": query_title, "y": year}, "omdb_title_year"
            )
            if result:
                return result
            result = _omdb_lookup(
                {"apikey": omdb_key, "t": query_title, "y": year - 1}, "omdb_title_year_minus1"
            )
            if result:
                return result
            result = _omdb_lookup(
                {"apikey": omdb_key, "t": query_title, "y": year + 1}, "omdb_title_year_plus1"
            )
            if result:
                return result

        result = _omdb_lookup({"apikey": omdb_key, "t": query_title}, "omdb_title_only")
        if result:
            return result

    if omdb_key:
        normalized_title = sanitized_title or normalize_title(title)
        result = _omdb_lookup({"apikey": omdb_key, "t": normalized_title}, "normalized")
        if result:
            return result

    if tmdb_candidate is not None:
        return None, "tmdb_only", tmdb_candidate

    return None, "lookup_failed", None


def process_record(
    record: Dict[str, Any],
    dry_run: bool,
    duplicates_path: pathlib.Path,
    provenance_source: str,
) -> Tuple[str, Optional[str]]:
    incoming_snapshot, incoming_hash = build_record_signature(record)
    try:
        with SessionLocal() as session:
            imdb_id = record.get("imdb_id")
            tmdb_id = record.get("tmdb_id")
            if imdb_id:
                stmt = select(Movie).where(Movie.imdb_id == imdb_id)
            elif tmdb_id:
                stmt = select(Movie).where(Movie.tmdb_id == tmdb_id)
            else:
                stmt = select(Movie).where(Movie.title == record["title"])
            existing = session.execute(stmt).scalar_one_or_none()

            genre_objs = [get_or_create_genre(session, name) for name in record["genres"]]
            mood_objs = [get_or_create_mood(session, name) for name in record["moods"]]

            if existing is None:
                movie = Movie(
                    title=record["title"],
                    year=record["year"],
                    runtime=record["runtime"],
                    plot=record["plot"],
                    imdb_id=record["imdb_id"],
                    tmdb_id=record["tmdb_id"],
                    imdb_rating=record.get("imdb_rating"),
                    imdb_votes=record.get("imdb_votes"),
                    rt_score=record.get("rt_score"),
                    where_to_watch=record.get("where_to_watch"),
                    languages=record.get("languages"),
                    countries=record.get("countries"),
                    collection=record.get("collection"),
                    poster_url=record["poster_url"],
                    backdrop_url=record["backdrop_url"],
                    genres=genre_objs,
                    moods=mood_objs,
                )
                session.add(movie)
                provenance = MovieIngestProvenance(
                    movie=movie,
                    source=provenance_source,
                    payload_hash=incoming_hash,
                    payload_snapshot=incoming_snapshot,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(provenance)
                session.flush()
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
                return "inserted", None
            else:
                provenance = session.get(MovieIngestProvenance, existing.id)
                if provenance and provenance.payload_hash == incoming_hash:
                    session.rollback()
                    _write_db_duplicate(record, duplicates_path)
                    return "skipped", "duplicate_payload"

                updated = False

                if record["title"] and record["title"] != existing.title:
                    existing.title = record["title"]
                    updated = True

                merged_year = _merge_values(existing.year, record["year"])
                if merged_year != existing.year:
                    existing.year = merged_year
                    updated = True

                merged_runtime = _merge_values(existing.runtime, record["runtime"])
                if merged_runtime != existing.runtime:
                    existing.runtime = merged_runtime
                    updated = True

                merged_plot = _merge_values(existing.plot, record["plot"])
                if merged_plot != existing.plot:
                    existing.plot = merged_plot
                    updated = True

                merged_tmdb = _merge_values(existing.tmdb_id, record["tmdb_id"])
                if merged_tmdb != existing.tmdb_id:
                    existing.tmdb_id = merged_tmdb
                    updated = True

                merged_rating = _merge_values(existing.imdb_rating, record.get("imdb_rating"))
                if merged_rating != existing.imdb_rating:
                    existing.imdb_rating = merged_rating
                    updated = True

                merged_votes = _merge_values(existing.imdb_votes, record.get("imdb_votes"))
                if merged_votes != existing.imdb_votes:
                    existing.imdb_votes = merged_votes
                    updated = True

                merged_rt = _merge_values(existing.rt_score, record.get("rt_score"))
                if merged_rt != existing.rt_score:
                    existing.rt_score = merged_rt
                    updated = True

                merged_poster = _merge_values(existing.poster_url, record["poster_url"])
                if merged_poster != existing.poster_url:
                    existing.poster_url = merged_poster
                    updated = True

                merged_backdrop = _merge_values(existing.backdrop_url, record["backdrop_url"])
                if merged_backdrop != existing.backdrop_url:
                    existing.backdrop_url = merged_backdrop
                    updated = True

                merged_where = merge_where_to_watch(
                    existing.where_to_watch, record.get("where_to_watch")
                )
                if merged_where != existing.where_to_watch:
                    existing.where_to_watch = merged_where
                    updated = True

                merged_languages = _merge_values(existing.languages, record.get("languages"))
                if merged_languages != existing.languages:
                    existing.languages = merged_languages
                    updated = True

                merged_countries = _merge_values(existing.countries, record.get("countries"))
                if merged_countries != existing.countries:
                    existing.countries = merged_countries
                    updated = True

                merged_collection = _merge_values(existing.collection, record.get("collection"))
                if merged_collection != existing.collection:
                    existing.collection = merged_collection
                    updated = True

                if genre_objs and {g.name for g in genre_objs} != {g.name for g in existing.genres}:
                    existing.genres = genre_objs
                    updated = True

                if mood_objs and {m.name for m in mood_objs} != {m.name for m in existing.moods}:
                    existing.moods = mood_objs
                    updated = True

                if not updated:
                    session.rollback()
                    _write_db_duplicate(record, duplicates_path)
                    return "skipped", "duplicate_db"

                snapshot_json, snapshot_hash = build_movie_signature(existing)
                if provenance is None:
                    provenance = MovieIngestProvenance(
                        movie=existing,
                        source=provenance_source,
                        payload_hash=snapshot_hash,
                        payload_snapshot=snapshot_json,
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(provenance)
                else:
                    provenance.source = provenance_source
                    provenance.payload_hash = snapshot_hash
                    provenance.payload_snapshot = snapshot_json
                    provenance.updated_at = datetime.now(timezone.utc)

                session.flush()
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
                return "updated", None
    except SQLAlchemyError as exc:
        raise RecoverableRowError(f"database error: {exc}") from exc


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    path = pathlib.Path(args.path)
    if not path.exists():
        logger.error("File not found: %s", path)
        return 2

    try:
        file_format = infer_format(path, args.format)
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    if engine.url.get_backend_name().startswith("sqlite"):
        Base.metadata.create_all(bind=engine)

    start_time = datetime.now()

    try:
        raw_rows = load_rows(path, file_format, args.encoding)
    except (MalformedRowError, json.JSONDecodeError) as exc:
        logger.error("Failed to load data: %s", exc)
        return 1

    dead_letter_dir = ROOT_DIR / "data"
    dead_letter_dir.mkdir(parents=True, exist_ok=True)
    dead_letter_path = dead_letter_dir / f"skips_{start_time:%Y%m%d_%H%M%S}.csv"
    with dead_letter_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row", "title", "year", "tmdb_imdb_id", "omdb_response", "omdb_error"])

    summary = Summary()
    seen_keys = set()
    reports_dir = ROOT_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    input_duplicates_path = reports_dir / "duplicates_in_input.csv"
    db_duplicates_path = reports_dir / "duplicates_in_db.csv"
    invalid_log_path = reports_dir / "invalid_imdb_id.csv"
    overrides_log_path = reports_dir / "overrides_used.csv"
    missing_log_path = reports_dir / "missing_imdb_id.csv"
    resolutions_log_path = reports_dir / "resolutions.csv"
    tmdb_only_log_path = reports_dir / "tmdb_only.csv"

    for path in (
        input_duplicates_path,
        db_duplicates_path,
        invalid_log_path,
        overrides_log_path,
        missing_log_path,
        resolutions_log_path,
        tmdb_only_log_path,
    ):
        if not path.exists():
            path.touch()

    overrides = load_overrides(ROOT_DIR / "scripts" / "overrides" / "imdb_map.csv")
    tmdb_key = os.getenv("TMDB_API_KEY")
    omdb_key = os.getenv("OMDB_API_KEY")
    allow_network = not args.no_network
    allow_tmdb_only = args.allow_tmdb_only

    for index, raw in enumerate(raw_rows, start=1):
        try:
            record = normalize_row(raw, index)
        except MalformedRowError as exc:
            summary.record_malformed(str(exc))
            logger.warning("Row %s malformed: %s", index, exc)
            continue

        imdb_id = record.get("imdb_id")
        original_imdb_id = record.get("imdb_id_original")
        initial_invalid = bool(record.get("imdb_invalid"))
        resolved_source = "csv"
        using_tmdb_only = False

        if imdb_id and original_imdb_id:
            normalized_original = normalize_imdb_id(original_imdb_id)
            if normalized_original == imdb_id and original_imdb_id.strip().lower() != imdb_id:
                resolved_source = "normalized"

        if not imdb_id:
            imdb_id = apply_overrides(record, overrides, index, overrides_log_path)
            if imdb_id:
                resolved_source = "override"

        tmdb_candidate: Optional[int] = None

        resolver_state.last_tmdb_imdb_id = None
        resolver_state.last_omdb_payload = None

        if not imdb_id:
            resolved, tag, tmdb_candidate = resolve_imdb_via_network(
                record,
                allow_network=allow_network,
                tmdb_key=tmdb_key,
                omdb_key=omdb_key,
            )
            if resolved:
                record["imdb_id"] = resolved
                imdb_id = resolved
                resolved_source = tag or "tmdb"
            elif tag == "tmdb_only" and allow_tmdb_only and tmdb_candidate:
                record_tmdb = record.get("tmdb_id")
                if not record_tmdb:
                    record["tmdb_id"] = tmdb_candidate
                using_tmdb_only = True
                resolved_source = "tmdb_only"
            elif tag == "tmdb_only":
                summary.record_skip("missing_imdb_id")
                logger.warning("Row %s skipped: missing_imdb_id", index)
                with missing_log_path.open("a", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow([index, record.get("title"), original_imdb_id])
                continue
            elif tag == "api_keys_missing":
                summary.record_skip("api_keys_missing")
                logger.warning("Row %s skipped: api_keys_missing", index)
                with missing_log_path.open("a", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow([index, record.get("title"), original_imdb_id])
                continue
            elif tag == "network_disabled":
                summary.record_skip("network_disabled")
                logger.warning("Row %s skipped: network disabled", index)
                with missing_log_path.open("a", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    writer.writerow([index, record.get("title"), original_imdb_id])
                continue

        if not imdb_id and not using_tmdb_only:
            reason = "invalid_imdb_id" if initial_invalid else "missing_imdb_id"
            summary.record_skip(reason)
            logger.warning("Row %s skipped: %s", index, reason)
            log_path = invalid_log_path if reason == "invalid_imdb_id" else missing_log_path
            with log_path.open("a", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow([index, record.get("title"), original_imdb_id])
            try:
                with dead_letter_path.open("a", encoding="utf-8", newline="") as fh:
                    writer = csv.writer(fh)
                    omdb_payload = resolver_state.last_omdb_payload or {}
                    writer.writerow(
                        [
                            index,
                            record.get("title"),
                            record.get("year"),
                            resolver_state.last_tmdb_imdb_id or "",
                            omdb_payload.get("Response"),
                            omdb_payload.get("Error"),
                        ]
                    )
            except OSError as exc:
                logger.warning("Failed to write dead-letter entry: %s", exc)
            continue

        if using_tmdb_only:
            with tmdb_only_log_path.open("a", encoding="utf-8", newline="") as fh2:
                writer2 = csv.writer(fh2)
                writer2.writerow(
                    [
                        index,
                        record.get("title"),
                        record.get("year"),
                        record.get("tmdb_id"),
                    ]
                )

        log_source = resolved_source
        if resolved_source == "override":
            log_source = "csv"

        with resolutions_log_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([index, record.get("title"), record.get("year"), imdb_id, log_source])

        if imdb_id:
            dedup_key = ("imdb", imdb_id.lower())
        elif record.get("tmdb_id"):
            dedup_key = ("tmdb", str(record.get("tmdb_id")))
        else:
            dedup_key = ("title", record.get("title").lower())

        if dedup_key in seen_keys:
            summary.record_skip("duplicate_input")
            logger.warning("Row %s skipped: duplicate entry in input", index)
            with input_duplicates_path.open("a", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    [
                        index,
                        record.get("title"),
                        record.get("imdb_id"),
                        record.get("tmdb_id"),
                    ]
                )
            continue
        seen_keys.add(dedup_key)

        try:
            action, reason = process_record(
                record,
                args.dry_run,
                db_duplicates_path,
                log_source,
            )
            if action == "inserted":
                summary.inserted += 1
            elif action == "updated":
                summary.updated += 1
            elif action == "skipped":
                summary.record_skip(reason or "skipped")
            else:
                summary.record_skip("unknown_action")
        except RecoverableRowError as exc:
            summary.record_skip("recoverable_error")
            logger.warning("Row %s skipped due to recoverable error: %s", index, exc)

    summary.log(args.dry_run)

    if summary.malformed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
