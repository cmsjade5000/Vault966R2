"""Retry resolving missing or invalid IMDb IDs and emit a patch file."""

from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
from typing import Dict, List, Optional, Tuple

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from scripts.etl_seed import (  # type: ignore
        load_overrides,
        normalize_title,
        resolve_imdb_via_network,
    )
except RuntimeError:
    from legacy.etl.etl_seed import (  # type: ignore
        load_overrides,
        normalize_title,
        resolve_imdb_via_network,
    )

REPORTS_DIR = ROOT_DIR / "reports"
DEFAULT_PATCH_PATH = REPORTS_DIR / "imdb_patch.json"
MISSING_REPORT = REPORTS_DIR / "missing_imdb_id.csv"
INVALID_REPORT = REPORTS_DIR / "invalid_imdb_id.csv"
OVERRIDES_LOG = REPORTS_DIR / "overrides_used.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry resolving missing IMDb IDs")
    parser.add_argument(
        "--missing-report",
        default=str(MISSING_REPORT),
        help="Path to missing_imdb_id.csv report",
    )
    parser.add_argument(
        "--invalid-report",
        default=str(INVALID_REPORT),
        help="Path to invalid_imdb_id.csv report",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_PATCH_PATH),
        help="Patch file to write (JSON or CSV based on extension)",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Disable network lookups for missing imdb_id",
    )
    return parser.parse_args()


def load_report(path: pathlib.Path) -> List[Dict[str, Optional[str]]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Optional[str]]] = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        for raw in reader:
            if not raw:
                continue
            title = raw[1].strip() if len(raw) > 1 and raw[1] else None
            if not title:
                continue
            entry = {
                "title": title,
                "original": raw[2].strip() if len(raw) > 2 and raw[2] else None,
            }
            rows.append(entry)
    return rows


def apply_overrides_local(
    title: str,
    overrides: Dict[Tuple[str, Optional[int]], str],
    log_path: pathlib.Path,
) -> Optional[str]:
    title_key = title.strip().lower()
    imdb_id = overrides.get((title_key, None))
    if imdb_id:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([title, imdb_id])
    return imdb_id


def write_patch(entries: List[Dict[str, Optional[str]]], output: pathlib.Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        with output.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["title", "year", "imdb_id", "tmdb_id"])
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)
    else:
        with output.open("w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)


def main() -> int:
    args = parse_args()
    overrides = load_overrides(ROOT_DIR / "scripts" / "overrides" / "imdb_map.csv")
    overrides_log = OVERRIDES_LOG

    missing_rows = load_report(pathlib.Path(args.missing_report))
    invalid_rows = load_report(pathlib.Path(args.invalid_report))
    candidates = missing_rows + invalid_rows

    if not candidates:
        print("No missing or invalid entries found.")
        return 0

    tmdb_key = os.getenv("TMDB_API_KEY")
    omdb_key = os.getenv("OMDB_API_KEY")

    resolved: List[Dict[str, Optional[str]]] = []
    still_missing: List[Dict[str, Optional[str]]] = []
    seen_titles = set()

    for entry in candidates:
        title = entry["title"]
        norm_title = normalize_title(title)
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)

        record = {
            "title": title,
            "year": None,
            "tmdb_id": None,
        }

        imdb_id = apply_overrides_local(title, overrides, overrides_log)
        source = "override" if imdb_id else None

        if not imdb_id:
            imdb_id, source_tag, tmdb_candidate = resolve_imdb_via_network(
                record,
                allow_network=not args.no_network,
                tmdb_key=tmdb_key,
                omdb_key=omdb_key,
                max_retries=2,
                retry_delay=0.2,
            )
            if source_tag == "tmdb_only" and tmdb_candidate:
                resolved.append(
                    {
                        "title": title,
                        "year": None,
                        "imdb_id": None,
                        "tmdb_id": str(tmdb_candidate),
                    }
                )
                print(f"TMDb-only resolution: {title} -> TMDb {tmdb_candidate}")
                continue
            source = source_tag

        if imdb_id:
            resolved.append(
                {
                    "title": title,
                    "year": None,
                    "imdb_id": imdb_id,
                    "tmdb_id": None,
                }
            )
            print(f"Resolved {title} -> {imdb_id} ({source})")
        else:
            still_missing.append(entry)
            print(f"Did not resolve {title}")

    write_patch(resolved, pathlib.Path(args.output))
    print(f"Resolved: {len(resolved)}")
    print(f"Still missing: {len(still_missing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
