"""Backfill missing IMDb/Rotten Tomatoes ratings in an enriched CSV via OMDb.

Related skill: `metadata-cleanup`.

Requires `OMDB_API_KEY` in the environment (or pass --omdb-key).

Example:
  python scripts/fill_missing_ratings_csv.py \
    --input data/enriched_movies_v2.csv \
    --output data/enriched_movies_v2.ratings.csv
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.utils.omdb import (
    extract_rotten_tomatoes_score,
    parse_imdb_rating,
    parse_imdb_votes,
)  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill ratings in enriched CSV via OMDb")
    parser.add_argument(
        "--input",
        default=str(ROOT / "data" / "enriched_movies_v2.csv"),
        help="Input CSV path (default: data/enriched_movies_v2.csv)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path (required).",
    )
    parser.add_argument(
        "--omdb-key",
        default=None,
        help="OMDb API key (default: env OMDB_API_KEY).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between OMDb requests (default: 0.25).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max rows to update (default: 0 = no limit).",
    )
    return parser.parse_args()


def needs_backfill(row: Dict[str, Any]) -> bool:
    if not str(row.get("imdb_id") or "").strip():
        return False
    missing_rating = not str(row.get("imdb_rating") or "").strip()
    missing_votes = not str(row.get("imdb_votes") or "").strip()
    missing_rt = not str(row.get("rt_score") or "").strip()
    return missing_rating or missing_votes or missing_rt


def fetch_omdb(client: httpx.Client, api_key: str, imdb_id: str) -> Optional[dict]:
    resp = client.get(
        "https://www.omdbapi.com/", params={"apikey": api_key, "i": imdb_id}, timeout=10.0
    )
    resp.raise_for_status()
    data = resp.json()
    if not data or str(data.get("Response")) != "True":
        return None
    return data


def apply_omdb(row: Dict[str, Any], omdb_payload: dict) -> bool:
    changed = False
    imdb_rating = parse_imdb_rating(omdb_payload.get("imdbRating"))
    if imdb_rating is not None and not str(row.get("imdb_rating") or "").strip():
        row["imdb_rating"] = str(imdb_rating)
        changed = True

    imdb_votes = parse_imdb_votes(omdb_payload.get("imdbVotes"))
    if imdb_votes is not None and not str(row.get("imdb_votes") or "").strip():
        row["imdb_votes"] = str(imdb_votes)
        changed = True

    rt_score = extract_rotten_tomatoes_score(omdb_payload)
    if rt_score is not None and not str(row.get("rt_score") or "").strip():
        row["rt_score"] = str(rt_score)
        changed = True

    return changed


def read_csv(path: pathlib.Path) -> tuple[list[str], list[Dict[str, Any]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, [dict(row) for row in reader]


def write_csv(
    path: pathlib.Path, fieldnames: Iterable[str], rows: Iterable[Dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    api_key = args.omdb_key or os.getenv("OMDB_API_KEY")
    if not api_key:
        raise SystemExit("OMDB_API_KEY is missing (set env var or pass --omdb-key)")

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    fieldnames, rows = read_csv(input_path)
    if not fieldnames:
        raise SystemExit(f"CSV appears to have no header: {input_path}")

    updated = 0
    attempted = 0

    with httpx.Client() as client:
        for row in rows:
            if args.limit and updated >= args.limit:
                break
            if not needs_backfill(row):
                continue
            imdb_id = str(row.get("imdb_id") or "").strip()
            if not imdb_id:
                continue
            attempted += 1
            payload = fetch_omdb(client, api_key, imdb_id)
            if payload and apply_omdb(row, payload):
                updated += 1
            if args.sleep:
                time.sleep(args.sleep)

    output_path = pathlib.Path(args.output)
    write_csv(output_path, fieldnames, rows)
    print(f"Attempted: {attempted} | updated: {updated} | wrote: {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
