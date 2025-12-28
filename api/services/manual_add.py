from __future__ import annotations

import csv
import pathlib
from typing import Iterable, Tuple

from core.enriched_csv import normalize_where_to_watch
from api.utils.providers import merge_providers

BASE_DIR = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def _normalize_key(title: str, year: int | None) -> Tuple[str, int | None]:
    normalized_title = title.strip().lower()
    return normalized_title, year if year is not None else None


def _load_existing_pairs(path: pathlib.Path) -> set[Tuple[str, int | None]]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return set()
        title_field = "title"
        year_field = "year"
        result: set[Tuple[str, int | None]] = set()
        for row in reader:
            title = (row.get(title_field) or "").strip()
            if not title:
                continue
            year_raw = row.get(year_field)
            try:
                year_value = int(year_raw) if year_raw not in (None, "") else None
            except ValueError:
                year_value = None
            result.add(_normalize_key(title, year_value))
        return result


def _append_row(path: pathlib.Path, fieldnames: Iterable[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    writer_fieldnames = list(fieldnames)
    if file_exists and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8", newline="") as read_handle:
            reader = csv.DictReader(read_handle)
            if reader.fieldnames:
                writer_fieldnames = list(reader.fieldnames)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=writer_fieldnames, extrasaction="ignore")
        write_header = not file_exists
        if not write_header and handle.tell() == 0:
            write_header = True
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _migrate_enriched_csv_schema(path: pathlib.Path, fieldnames: list[str]) -> None:
    """Rewrite enriched_movies.csv in-place if it still contains legacy columns."""

    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        existing_fields = list(reader.fieldnames or [])
        if not existing_fields:
            return
        if "where_to_watch" not in existing_fields:
            return
        rows = [dict(row) for row in reader]

    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            legacy = (row.get("where_to_watch") or "").strip()
            watch = normalize_where_to_watch(legacy, region="US")
            row.pop("where_to_watch", None)
            row.setdefault("watch_region", "US")
            row.setdefault("providers_stream", "; ".join(watch.stream))
            row.setdefault("providers_rent", "; ".join(watch.rent))
            row.setdefault("providers_buy", "; ".join(watch.buy))
            row.setdefault("tmdb_watch_url", watch.tmdb_watch_url or "")
            writer.writerow(row)
    tmp_path.replace(path)


def append_movie_to_cleaned_csv(title: str, year: int | None) -> bool:
    """Append to data/cleaned_titles.csv when not already present.

    Returns True if a row was written, False when duplicate.
    """

    path = DATA_DIR / "cleaned_titles.csv"
    existing = _load_existing_pairs(path)
    key = _normalize_key(title, year)
    if key in existing:
        return False

    row = {"title": title.strip(), "year": year or ""}
    _append_row(path, ["title", "year"], row)
    return True


def append_movie_to_enriched_csv(
    title: str,
    year: int | None,
    metadata: dict | None = None,
    providers: list[str] | None = None,
) -> bool:
    """Append a row to data/enriched_movies.csv if missing.

    When metadata is provided, it is used to populate known columns; otherwise the
    entry is added as a placeholder for later enrichment.
    """

    path = DATA_DIR / "enriched_movies.csv"
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
    _migrate_enriched_csv_schema(path, fieldnames)

    existing = _load_existing_pairs(path)
    key = _normalize_key(title, year)
    if key in existing:
        return False

    row = {name: "" for name in fieldnames}
    row["title"] = title.strip()
    row["year"] = year or ""
    row["watch_region"] = "US"

    provider_list = merge_providers(providers or [], (metadata or {}).get("where_to_watch"))

    if metadata:
        row["imdb_id"] = metadata.get("imdb_id") or ""
        row["tmdb_id"] = metadata.get("tmdb_id") or ""
        row["runtime_min"] = metadata.get("runtime") or ""
        row["plot"] = metadata.get("overview") or ""
        row["poster_url"] = metadata.get("poster_url") or ""
        row["backdrop_url"] = metadata.get("backdrop_url") or ""
        row["genres"] = "; ".join(metadata.get("genres", []) or [])
        keywords = metadata.get("keywords") or []
        if keywords:
            row["keywords"] = "; ".join(keywords)
        row["tmdb_last_scraped"] = metadata.get("release_date") or ""

    if provider_list:
        row["providers_stream"] = "; ".join(provider_list)

    _append_row(path, fieldnames, row)
    return True
