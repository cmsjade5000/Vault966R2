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
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import api.models  # noqa: F401  # ensure all ORM mappers are registered (e.g., MovieFlag)
from core.movie_metadata import MovieMetadata
from core.vault_ids import normalize_vault_id

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from api.db import Base, SessionLocal, engine
from api.models.movie import Genre, Mood, Movie, MovieIngestProvenance


@dataclass
class ProvenanceContext:
    provider: str
    provider_id: Optional[str]
    payload_sha: Optional[str]
    source_url: Optional[str]
    notes: Optional[str] = None


from api.models.person import Person, Role, RoleType
from api.utils.providers import collect_provider_tokens, merge_providers

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
        "--allow-unidentified",
        action="store_true",
        help="Allow inserts without IMDb/TMDb IDs using title/year identity",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Max HTTP retries for TMDb/OMDb lookups (default: 2).",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.2,
        help="Delay in seconds between HTTP retries (default: 0.2).",
    )
    parser.add_argument(
        "--reports-dir",
        type=pathlib.Path,
        default=ROOT_DIR / "reports",
        help="Directory for import audit logs (default: reports/).",
    )
    parser.add_argument(
        "--dead-letter-dir",
        type=pathlib.Path,
        default=ROOT_DIR / "data",
        help="Directory for skipped-row logs (default: data/).",
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

        # Remove BOM if present on header line
        csv_lines[0] = csv_lines[0].lstrip("\ufeff")
        reader = csv.DictReader(csv_lines)

        rows: List[Dict[str, Any]] = []
        for row in reader:
            cleaned = {key: value for key, value in row.items() if key is not None}
            rows.append(cleaned)
        return rows


def _http_get_with_retries(
    url: str,
    *,
    params: Dict[str, Any],
    timeout: float,
    max_retries: int,
    retry_delay: float,
    tag: str,
) -> Optional[httpx.Response]:
    """HTTP GET with simple retry/backoff. Returns None after exhausting retries."""
    attempt = 0
    while True:
        try:
            resp = httpx.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            attempt += 1
            if attempt > max_retries:
                logger.warning("%s lookup failed after %s attempts: %s", tag, attempt - 1, exc)
                return None
            time.sleep(retry_delay)


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
    without_brackets = re.sub(r"\s*\[[^\]]*\]\s*", " ", without_parentheticals)
    part_normalized = re.sub(
        r"\bpart\s+([ivx]+)\b",
        lambda m: f"Part { {'i':'1','ii':'2','iii':'3','iv':'4','v':'5','vi':'6','vii':'7','viii':'8','ix':'9','x':'10'}.get(m.group(1).lower(), m.group(1)) }",
        without_brackets,
        flags=re.IGNORECASE,
    )
    sanitized = normalize_title(part_normalized)
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


def coerce_int(value: Any) -> Optional[int]:
    if value in _NULL_STRINGS:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text in _NULL_STRINGS:
        return None
    try:
        if "." in text:
            return int(float(text))
        return int(text)
    except ValueError:
        return None


def split_multi(value: Any) -> List[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        candidates = value
    else:
        candidates = [part.strip() for part in re.split(r"[|;,]", str(value)) if part.strip()]

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


def coerce_float(value: Any) -> Optional[float]:
    if value in _NULL_STRINGS:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text or text in _NULL_STRINGS:
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def clean_text(value: Any) -> Optional[str]:
    if value in _NULL_STRINGS:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_providers(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str) and value in _NULL_STRINGS:
        return []
    return collect_provider_tokens(value)


# Merge helpers for JSONB providers
def _merge_provider_lists(a, b):
    """Merge lists of provider dicts, de-duplicating by provider_id or provider_name."""
    if not isinstance(a, list):
        a = []
    if not isinstance(b, list):
        b = []
    index = {}
    for item in a:
        if not isinstance(item, dict):
            continue
        key = item.get("provider_id") or item.get("provider_name") or str(item)
        index[key] = item
    for item in b:
        if not isinstance(item, dict):
            continue
        key = item.get("provider_id") or item.get("provider_name") or str(item)
        if key not in index:
            index[key] = item
    return list(index.values())


def _merge_providers_json(existing: dict, new: dict) -> dict:
    """Deep-merge TMDb watch/providers dicts by country code; keep unique providers."""
    if not isinstance(existing, dict):
        existing = {}
    if not isinstance(new, dict):
        new = {}
    merged = {**existing}
    for cc, pdata in new.items():
        if not isinstance(pdata, dict):
            continue
        base = merged.get(cc, {})
        out = dict(base)
        for key, val in pdata.items():
            if isinstance(val, list):
                out[key] = _merge_provider_lists(base.get(key, []), val)
            else:
                out[key] = val if val not in (None, "", []) else base.get(key)
        merged[cc] = out
    return merged


def normalize_providers(value: Any) -> Optional[List[str]]:
    providers = merge_providers(_split_providers(value))
    return providers or None


def merge_where_to_watch(existing_value: Any, new_value: Any) -> Optional[List[str]]:
    providers = merge_providers(_split_providers(existing_value), _split_providers(new_value))
    return providers or None


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

    canonical = MovieMetadata.from_mapping({**raw, "title": title, "imdb_id": imdb_id})
    record = canonical.to_import_record()
    record.update(
        {
            "imdb_id_original": imdb_id_raw,
            "imdb_invalid": imdb_invalid,
            "legacy_vault_id": _first_value(raw, ["vault_id", "legacy_vault_id"]),
        }
    )
    return record


def _canonicalize_for_hash(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_for_hash(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [_canonicalize_for_hash(item) for item in value]
        if all(isinstance(item, str) for item in normalized):
            return sorted(normalized, key=str.casefold)
        return normalized
    return value


def compute_payload_sha(record: Dict[str, Any]) -> str:
    canonical = {key: _canonicalize_for_hash(value) for key, value in record.items()}
    serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def determine_provenance_provider_id(record: Dict[str, Any]) -> Optional[str]:
    legacy_vault_id = record.get("legacy_vault_id")
    if legacy_vault_id:
        return str(legacy_vault_id)
    imdb_id = record.get("imdb_id")
    if imdb_id:
        return str(imdb_id)
    tmdb_id = record.get("tmdb_id")
    if tmdb_id:
        return f"tmdb:{tmdb_id}"
    title = record.get("title")
    if not title:
        return None
    year = record.get("year")
    if year:
        return f"{title} ({year})"
    return str(title)


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


def get_or_create_person(session, name: str) -> Person:
    cleaned = name.strip()
    stmt = select(Person).where(
        func.lower(Person.name) == cleaned.lower(),
        Person.tmdb_id.is_(None),
    )
    person = session.execute(stmt).scalar_one_or_none()
    if person is None:
        person = Person(name=cleaned)
        session.add(person)
        session.flush()
    return person


def sync_people_roles(session, movie: Movie, record: Dict[str, Any]) -> None:
    role_groups = (
        (RoleType.DIRECTOR, record.get("directors") or []),
        (RoleType.ACTOR, record.get("cast") or []),
    )
    for role_type, names in role_groups:
        if not names:
            continue
        existing = [role for role in movie.roles if role.role_type == role_type]
        for role in existing:
            session.delete(role)
        for billing_order, name in enumerate(names):
            person = get_or_create_person(session, name)
            movie.roles.append(
                Role(
                    person=person,
                    role_type=role_type,
                    billing_order=billing_order,
                )
            )


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
        or existing.awards != record.get("awards")
        or existing.imdb_id != record["imdb_id"]
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


def _is_nullish(value: Optional[Any]) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value in _NULL_STRINGS
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return value in _NULL_STRINGS


def _merge_values(existing_value: Optional[Any], new_value: Optional[Any]) -> Optional[Any]:
    if _is_nullish(new_value):
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


def _upsert_movie_provenance(
    session,
    movie: Movie,
    provenance: ProvenanceContext,
) -> None:
    if provenance is None:
        return

    stmt = select(MovieIngestProvenance).where(
        MovieIngestProvenance.movie_id == movie.id,
        MovieIngestProvenance.provider == provenance.provider,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing is None:
        session.add(
            MovieIngestProvenance(
                movie_id=movie.id,
                provider=provenance.provider,
                provider_id=provenance.provider_id,
                payload_sha=provenance.payload_sha,
                source_url=provenance.source_url,
                notes=provenance.notes,
            )
        )
        return

    updated = False
    if provenance.provider_id is not None and existing.provider_id != provenance.provider_id:
        existing.provider_id = provenance.provider_id
        updated = True
    if provenance.payload_sha is not None and existing.payload_sha != provenance.payload_sha:
        existing.payload_sha = provenance.payload_sha
        updated = True
    if provenance.source_url is not None and existing.source_url != provenance.source_url:
        existing.source_url = provenance.source_url
        updated = True
    if provenance.notes is not None and existing.notes != provenance.notes:
        existing.notes = provenance.notes
        updated = True

    if updated:
        session.add(existing)


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
    max_retries: int,
    retry_delay: float,
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

            def _tmdb_search(query: str, yr: Optional[int], tag_suffix: str) -> Optional[str]:
                nonlocal tmdb_candidate
                params = {"query": query, "api_key": tmdb_key}
                if yr:
                    params["year"] = yr
                response = _http_get_with_retries(
                    "https://api.themoviedb.org/3/search/movie",
                    params=params,
                    timeout=10.0,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    tag=f"TMDb search {tag_suffix}",
                )
                data = response.json() if response is not None else {"results": []}
                results = data.get("results", [])
                for result in results:
                    result_title = str(result.get("title", ""))
                    if sanitize_title_for_search(result_title) != sanitize_title_for_search(query):
                        continue
                    release_date = result.get("release_date") or ""
                    release_year = int(release_date[:4]) if release_date[:4].isdigit() else None
                    if yr and release_year and abs(release_year - yr) > 2:
                        continue
                    tmdb_id = result.get("id")
                    if not tmdb_id:
                        continue
                    tmdb_candidate = tmdb_id
                    external = _http_get_with_retries(
                        f"https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids",
                        params={"api_key": tmdb_key},
                        timeout=10.0,
                        max_retries=max_retries,
                        retry_delay=retry_delay,
                        tag="TMDb external_ids",
                    )
                    external_payload = external.json() if external is not None else {}
                    imdb_id = extract_imdb_from_tmdb_external_ids(external_payload)
                    if imdb_id:
                        resolver_state.last_tmdb_imdb_id = imdb_id
                        return imdb_id
                    resolver_state.last_tmdb_imdb_id = extract_imdb_from_tmdb_external_ids(
                        external_payload
                    )
                return None

            # Try strict + small fallbacks (title-only / year tolerance / alias cleaned).
            title_variants = [sanitized_title]
            for query in title_variants:
                if year:
                    for candidate_year in (year, year - 1, year + 1, year - 2, year + 2):
                        resolved = _tmdb_search(query, candidate_year, f"{candidate_year}")
                        if resolved:
                            return resolved, "tmdb", tmdb_candidate
                resolved = _tmdb_search(query, None, "title_only")
                if resolved:
                    return resolved, "tmdb", tmdb_candidate
        except httpx.HTTPError as exc:
            logger.warning("TMDb lookup failed: %s", exc)

    def _omdb_lookup(params: Dict[str, Any], tag: str) -> Optional[Tuple[str, str, Optional[int]]]:
        # Use a copy so we can mutate for logging/testing without affecting callers.
        query_params = dict(params)
        response = _http_get_with_retries(
            "https://www.omdbapi.com/",
            params=query_params,
            timeout=10.0,
            max_retries=max_retries,
            retry_delay=retry_delay,
            tag=f"OMDb {tag}",
        )
        if response is None:
            return None
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
    provenance: Optional[ProvenanceContext] = None,
) -> Tuple[str, Optional[str]]:
    try:
        with SessionLocal() as session:
            imdb_id = record.get("imdb_id")
            tmdb_id = record.get("tmdb_id")
            existing = None
            if imdb_id:
                stmt = select(Movie).where(Movie.imdb_id == imdb_id)
                existing = session.execute(stmt).scalar_one_or_none()

            if existing is None and tmdb_id:
                stmt = select(Movie).where(Movie.tmdb_id == tmdb_id)
                existing = session.execute(stmt).scalar_one_or_none()

            if existing is None and not imdb_id and not tmdb_id:
                stmt = select(Movie).where(Movie.title == record["title"])
                existing = session.execute(stmt).scalar_one_or_none()

            if existing is not None:
                incoming_title = normalize_title(record["title"])
                existing_title = normalize_title(existing.title)
                incoming_year = record.get("year")
                existing_year = existing.year
                title_conflict = incoming_title != existing_title
                year_conflict = (
                    incoming_year is not None
                    and existing_year is not None
                    and incoming_year != existing_year
                )
                if title_conflict or year_conflict:
                    session.rollback()
                    _write_db_duplicate(record, duplicates_path)
                    return "skipped", "identifier_conflict"

            genre_objs = [get_or_create_genre(session, name) for name in record["genres"]]
            mood_objs = [get_or_create_mood(session, name) for name in record["moods"]]

            if existing is None:
                movie = Movie(
                    vault_id=normalize_vault_id(record.get("legacy_vault_id")),
                    title=record["title"],
                    year=record["year"],
                    runtime=record["runtime"],
                    plot=record["plot"],
                    awards=record.get("awards"),
                    certificate=record.get("certificate"),
                    keywords=record.get("keywords") or None,
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
                session.flush()
                sync_people_roles(session, movie, record)
                _upsert_movie_provenance(session, movie, provenance)
                session.flush()
                if dry_run:
                    session.rollback()
                else:
                    session.commit()
                return "inserted", None
            else:
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

                merged_awards = _merge_values(existing.awards, record.get("awards"))
                if merged_awards != existing.awards:
                    existing.awards = merged_awards
                    updated = True

                merged_certificate = _merge_values(existing.certificate, record.get("certificate"))
                if merged_certificate != existing.certificate:
                    existing.certificate = merged_certificate
                    updated = True

                merged_keywords = _merge_values(existing.keywords, record.get("keywords") or None)
                if merged_keywords != existing.keywords:
                    existing.keywords = merged_keywords
                    updated = True

                merged_imdb = _merge_values(existing.imdb_id, record["imdb_id"])
                if merged_imdb != existing.imdb_id:
                    existing.imdb_id = merged_imdb
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

                if record.get("directors") or record.get("cast"):
                    sync_people_roles(session, existing, record)
                    updated = True

                if not updated:
                    session.rollback()
                    _write_db_duplicate(record, duplicates_path)
                    return "skipped", "duplicate_db"

                _upsert_movie_provenance(session, existing, provenance)
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

    dead_letter_dir = args.dead_letter_dir
    dead_letter_dir.mkdir(parents=True, exist_ok=True)
    dead_letter_path = dead_letter_dir / f"skips_{start_time:%Y%m%d_%H%M%S}.csv"
    with dead_letter_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["row", "title", "year", "tmdb_imdb_id", "omdb_response", "omdb_error"])

    summary = Summary()
    seen_keys = set()
    reports_dir = args.reports_dir
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
        using_unidentified = False

        if imdb_id and original_imdb_id:
            normalized_original = normalize_imdb_id(original_imdb_id)
            if normalized_original == imdb_id and original_imdb_id.strip().lower() != imdb_id:
                resolved_source = "normalized"

        if not imdb_id and allow_tmdb_only and record.get("tmdb_id"):
            using_tmdb_only = True
            resolved_source = "tmdb_only"

        if (
            not imdb_id
            and not record.get("tmdb_id")
            and args.allow_unidentified
            and record.get("title")
        ):
            using_unidentified = True
            resolved_source = "title_year"

        if not imdb_id and not using_tmdb_only and not using_unidentified:
            imdb_id = apply_overrides(record, overrides, index, overrides_log_path)
            if imdb_id:
                resolved_source = "override"

        tmdb_candidate: Optional[int] = None

        resolver_state.last_tmdb_imdb_id = None
        resolver_state.last_omdb_payload = None

        if not imdb_id and not using_tmdb_only and not using_unidentified:
            resolved, tag, tmdb_candidate = resolve_imdb_via_network(
                record,
                allow_network=allow_network,
                tmdb_key=tmdb_key,
                omdb_key=omdb_key,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
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

        if not imdb_id and not using_tmdb_only and not using_unidentified:
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

        payload_sha = compute_payload_sha(record)
        provenance = ProvenanceContext(
            provider="legacy_vault_csv" if record.get("legacy_vault_id") else "etl_seed",
            provider_id=determine_provenance_provider_id(record),
            payload_sha=payload_sha,
            source_url=str(path),
            notes=f"Row {index} from {path.name}",
        )

        try:
            action, reason = process_record(record, args.dry_run, db_duplicates_path, provenance)
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
