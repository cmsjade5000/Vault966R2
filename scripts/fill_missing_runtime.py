"""Backfill missing runtime_min values in an enriched CSV via TMDb/OMDb.

Requires TMDB_API_KEY and/or OMDB_API_KEY in the environment (or pass --tmdb-key/--omdb-key).
Falls back to TMDb title/year search when IDs are missing.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import os
import pathlib
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.enriched_csv import parse_int  # noqa: E402


TMDB_API_BASE = "https://api.themoviedb.org/3"
OMDB_API_BASE = "https://www.omdbapi.com/"

ROMAN_NUMERALS = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}


@dataclass
class BackfillResult:
    runtime_min: Optional[int]
    source: str
    tmdb_id: Optional[int] = None
    match_confidence: Optional[float] = None
    matched_title: Optional[str] = None
    matched_year: Optional[int] = None
    match_strategy: Optional[str] = None
    note: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill runtimes in enriched CSV via TMDb/OMDb")
    parser.add_argument(
        "--input",
        default=None,
        help="Input CSV (default: most recent enriched_movies*.csv in data/).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: data/<input>_runtime_<stamp>.csv).",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT / "reports" / "runtime_backfill.csv"),
        help="CSV report path (default: reports/runtime_backfill.csv).",
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
        "--sleep",
        type=float,
        default=0.25,
        help="Seconds to sleep between API requests (default: 0.25).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max rows to update (default: 0 = no limit).",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="Min TMDb match confidence for title/year fallback (default: 0.8).",
    )
    parser.add_argument(
        "--update-tmdb-id",
        action="store_true",
        help="Populate tmdb_id when a fallback TMDb match is accepted.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input CSV (writes via temp file).",
    )
    return parser.parse_args()


def _strip_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _latest_enriched_csv() -> pathlib.Path:
    if not DATA_DIR.exists():
        raise SystemExit(f"Data directory not found: {DATA_DIR}")
    candidates = []
    for path in DATA_DIR.glob("enriched_movies*.csv"):
        name = path.name
        if "needs_review" in name or "quarantine" in name:
            continue
        if path.is_file():
            candidates.append(path)
    if not candidates:
        raise SystemExit("No enriched_movies*.csv found in data/.")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _clean_title_aliases(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.replace("&", "and")
    cleaned = re.sub(
        r"\bpart\s+([ivx]+)\b",
        lambda m: f"part {ROMAN_NUMERALS.get(m.group(1).lower(), m.group(1))}",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def iter_tmdb_search_variants(title: str, year: int | None) -> List[Tuple[str, Optional[int], str]]:
    variants: List[Tuple[str, Optional[int], str]] = []
    base = title.strip()
    cleaned = _clean_title_aliases(base)
    for query, tag in ((base, "exact"), (cleaned, "alias_cleaned")):
        variants.append((query, year, tag))
        if year is not None:
            for delta in (1, -1, 2, -2):
                variants.append((query, year + delta, f"{tag}_year_{delta:+d}"))
        variants.append((query, None, f"{tag}_title_only"))

    seen: set[Tuple[str, Optional[int]]] = set()
    deduped: List[Tuple[str, Optional[int], str]] = []
    for query, yr, tag in variants:
        key = (query.lower().strip(), yr)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((query, yr, tag))
    return deduped


def _compute_match_confidence(
    requested_title: str,
    requested_year: int | None,
    matched_title: str,
    matched_year: int | None,
    strategy: str,
) -> float:
    def norm(value: str) -> str:
        return _clean_title_aliases(value).lower()

    ratio = difflib.SequenceMatcher(a=norm(requested_title), b=norm(matched_title)).ratio()
    year_bonus = 0.0
    if requested_year is not None and matched_year is not None:
        delta = abs(requested_year - matched_year)
        year_bonus = 0.15 if delta == 0 else 0.08 if delta == 1 else 0.03 if delta == 2 else -0.08
    penalty = 0.08 if "title_only" in strategy else 0.0
    confidence = max(0.0, min(1.0, ratio + year_bonus - penalty))
    return float(round(confidence, 3))


def _parse_release_year(value: str | None) -> Optional[int]:
    if not value:
        return None
    text = value.strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def _parse_runtime_omdb(value: Any) -> Optional[int]:
    text = _strip_value(value)
    if not text or text.upper() == "N/A":
        return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    runtime = parse_int(match.group(1))
    return runtime if runtime and runtime > 0 else None


def _tmdb_search(client: httpx.Client, api_key: str, query: str, year: Optional[int]) -> List[dict]:
    params: dict[str, Any] = {"api_key": api_key, "query": query, "include_adult": "false"}
    if year is not None:
        params["year"] = year
    response = client.get("/search/movie", params=params, timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    results = payload.get("results", [])
    return results if isinstance(results, list) else []


def _tmdb_detail(client: httpx.Client, api_key: str, tmdb_id: int) -> dict:
    response = client.get(f"/movie/{tmdb_id}", params={"api_key": api_key}, timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _omdb_detail(client: httpx.Client, api_key: str, imdb_id: str) -> dict:
    response = client.get(OMDB_API_BASE, params={"apikey": api_key, "i": imdb_id}, timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _search_tmdb_candidate(
    client: httpx.Client,
    api_key: str,
    title: str,
    year: Optional[int],
) -> Optional[BackfillResult]:
    for query, yr, strategy in iter_tmdb_search_variants(title, year):
        results = _tmdb_search(client, api_key, query, yr)
        if not results:
            continue
        best = None
        for item in results:
            tmdb_id = item.get("id")
            matched_title = item.get("title") or item.get("name") or ""
            matched_year = _parse_release_year(item.get("release_date") or "")
            confidence = _compute_match_confidence(
                title, year, matched_title, matched_year, strategy
            )
            if not best or confidence > best.match_confidence:
                best = BackfillResult(
                    runtime_min=None,
                    source="tmdb_search",
                    tmdb_id=int(tmdb_id) if tmdb_id else None,
                    match_confidence=confidence,
                    matched_title=matched_title,
                    matched_year=matched_year,
                    match_strategy=strategy,
                )
        return best
    return None


def needs_runtime(row: Dict[str, Any]) -> bool:
    runtime = parse_int(row.get("runtime_min"))
    return not runtime or runtime <= 0


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
    tmdb_key = args.tmdb_key or os.getenv("TMDB_API_KEY")
    omdb_key = args.omdb_key or os.getenv("OMDB_API_KEY")
    if not tmdb_key and not omdb_key:
        raise SystemExit("TMDB_API_KEY or OMDB_API_KEY is required to backfill runtimes.")

    input_path = pathlib.Path(args.input) if args.input else _latest_enriched_csv()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    default_output = DATA_DIR / f"{input_path.stem}_runtime_{stamp}.csv"
    output_path = input_path if args.in_place else pathlib.Path(args.output or default_output)

    fieldnames, rows = read_csv(input_path)
    if not fieldnames:
        raise SystemExit(f"CSV appears to have no header: {input_path}")
    if "runtime_min" not in fieldnames:
        fieldnames.append("runtime_min")

    report_rows: list[Dict[str, Any]] = []
    updated = 0
    attempted = 0

    tmdb_client = httpx.Client(base_url=TMDB_API_BASE) if tmdb_key else None
    omdb_client = httpx.Client() if omdb_key else None

    try:
        for row in rows:
            if args.limit and updated >= args.limit:
                break
            if not needs_runtime(row):
                continue

            title = _strip_value(row.get("title"))
            year = parse_int(row.get("year"))
            tmdb_id_raw = _strip_value(row.get("tmdb_id"))
            imdb_id = _strip_value(row.get("imdb_id"))
            result: Optional[BackfillResult] = None

            if tmdb_key and tmdb_client and tmdb_id_raw.isdigit():
                attempted += 1
                payload = _tmdb_detail(tmdb_client, tmdb_key, int(tmdb_id_raw))
                runtime = parse_int(payload.get("runtime"))
                if runtime and runtime > 0:
                    result = BackfillResult(
                        runtime_min=runtime, source="tmdb_id", tmdb_id=int(tmdb_id_raw)
                    )
                if args.sleep:
                    time.sleep(args.sleep)

            if result is None and omdb_key and omdb_client and imdb_id:
                attempted += 1
                payload = _omdb_detail(omdb_client, omdb_key, imdb_id)
                runtime = _parse_runtime_omdb(payload.get("Runtime"))
                if runtime:
                    result = BackfillResult(runtime_min=runtime, source="omdb_id")
                if args.sleep:
                    time.sleep(args.sleep)

            if result is None and tmdb_key and tmdb_client and title:
                attempted += 1
                candidate = _search_tmdb_candidate(tmdb_client, tmdb_key, title, year)
                if candidate and candidate.tmdb_id and candidate.match_confidence is not None:
                    if candidate.match_confidence >= args.min_confidence:
                        payload = _tmdb_detail(tmdb_client, tmdb_key, candidate.tmdb_id)
                        runtime = parse_int(payload.get("runtime"))
                        if runtime and runtime > 0:
                            candidate.runtime_min = runtime
                            result = candidate
                            if args.update_tmdb_id and not tmdb_id_raw:
                                row["tmdb_id"] = str(candidate.tmdb_id)
                    else:
                        candidate.note = "below_min_confidence"
                        result = candidate
                if args.sleep:
                    time.sleep(args.sleep)

            if result and result.runtime_min:
                row["runtime_min"] = str(result.runtime_min)
                updated += 1

            report_rows.append(
                {
                    "title": title,
                    "year": year or "",
                    "imdb_id": imdb_id,
                    "tmdb_id": _strip_value(row.get("tmdb_id")),
                    "status": "updated" if result and result.runtime_min else "missing",
                    "runtime_min": result.runtime_min if result else "",
                    "source": result.source if result else "",
                    "match_confidence": result.match_confidence if result else "",
                    "matched_title": result.matched_title if result else "",
                    "matched_year": result.matched_year if result else "",
                    "match_strategy": result.match_strategy if result else "",
                    "note": result.note if result else "",
                }
            )
    finally:
        if tmdb_client:
            tmdb_client.close()
        if omdb_client:
            omdb_client.close()

    if args.in_place:
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        write_csv(temp_path, fieldnames, rows)
        shutil.move(str(temp_path), str(output_path))
    else:
        write_csv(output_path, fieldnames, rows)

    if args.report:
        write_report(pathlib.Path(args.report), report_rows)

    print(f"Attempted: {attempted} | updated: {updated} | wrote: {output_path}")
    if args.report:
        print(f"Report: {args.report}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
