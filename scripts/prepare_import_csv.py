"""CLI helper to sanitize raw movie CSV data before running etl_seed.py.

Related skill: `csv-import-guard`.

Usage:
    python scripts/prepare_import_csv.py --input dirty.csv --output cleaned.csv

Steps performed:
  * Removes leading garbage rows so the first row is the header containing
    at least `title` and `year`.
  * Strips parenthetical descriptors (e.g. "(Unrated)", "(1988)") from titles
    and collapses whitespace.
  * Normalizes year values to four-digit integers where possible; rows with
    unparseable years are flagged in the summary.
  * Writes a CSV summary file alongside the output listing rows that still
    need manual attention.

This script does not hit any external APIs and is safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "data"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

TITLE_CLEAN_RE = re.compile(r"\s*\([^)]*\)\s*")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class Summary:
    total_rows: int = 0
    cleaned_titles: int = 0
    cleaned_years: int = 0
    skipped_rows: List[int] = field(default_factory=list)

    def log_skipped(self, row_number: int) -> None:
        self.skipped_rows.append(row_number)


def sanitize_title(title: str) -> str:
    cleaned = TITLE_CLEAN_RE.sub(" ", title).strip()
    cleaned = WHITESPACE_RE.sub(" ", cleaned)
    return cleaned


def sanitize_year(value: str) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    # Extract the first four consecutive digits.
    match = re.search(r"(\d{4})", text)
    if not match:
        return None
    year = int(match.group(1))
    if year < 1870 or year > 2100:
        return None
    return year


def _normalized_header(columns: List[str]) -> set[str]:
    return {str(column or "").strip().casefold() for column in columns}


def _canonical_header(columns: List[str]) -> List[str]:
    canonical: List[str] = []
    for column in columns:
        label = str(column or "").strip()
        folded = label.casefold()
        canonical.append(folded if folded in {"title", "year"} else label)
    return canonical


def load_rows(path: pathlib.Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        for columns in reader:
            header = _normalized_header(columns)
            if "title" in header:
                dict_reader = csv.DictReader(fh, fieldnames=_canonical_header(columns))
                return [dict(row) for row in dict_reader]
    return []


def clean_rows(rows: List[Dict[str, Any]], summary: Summary) -> List[Dict[str, Any]]:
    cleaned_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        summary.total_rows += 1

        if "title" not in row:
            summary.log_skipped(idx)
            continue

        raw_title = str(row["title"] or "").strip()
        cleaned_title = sanitize_title(raw_title)
        if cleaned_title != raw_title:
            summary.cleaned_titles += 1
        row["title"] = cleaned_title

        raw_year = row.get("year", "")
        cleaned_year = sanitize_year(str(raw_year)) if raw_year is not None else None
        if cleaned_year is None and raw_year:
            summary.log_skipped(idx)
        else:
            if str(raw_year).strip() != "" and str(raw_year).strip() != str(cleaned_year):
                summary.cleaned_years += 1
            row["year"] = cleaned_year if cleaned_year is not None else ""

        cleaned_rows.append(row)

    return cleaned_rows


def write_output(rows: List[Dict[str, Any]], output_path: pathlib.Path) -> None:
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(summary: Summary, output_path: pathlib.Path) -> None:
    summary_path = SUMMARY_DIR / f"prepare_summary_{output_path.stem}.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        writer.writerow(["total_rows", summary.total_rows])
        writer.writerow(["cleaned_titles", summary.cleaned_titles])
        writer.writerow(["cleaned_years", summary.cleaned_years])
        writer.writerow(["rows_needing_manual_review", ";".join(map(str, summary.skipped_rows))])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize movie CSV before import")
    parser.add_argument("--input", required=True, help="Path to the raw CSV")
    parser.add_argument("--output", required=True, help="Path for the cleaned CSV")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    rows = load_rows(input_path)
    summary = Summary()
    cleaned = clean_rows(rows, summary)

    write_output(cleaned, output_path)
    write_summary(summary, output_path)

    print(
        "Sanitized CSV written to",
        output_path,
        "| total rows:",
        summary.total_rows,
        "| cleaned titles:",
        summary.cleaned_titles,
        "| cleaned years:",
        summary.cleaned_years,
        "| manual review rows:",
        len(summary.skipped_rows),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
