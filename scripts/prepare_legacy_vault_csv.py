"""Stage the legacy 21-column Vault CSV without importing it.

The staged CSV uses canonical field names and JSON-encoded arrays for values
that should remain arrays when the row is later converted to JSON. A separate
JSON report records data-quality issues for human or automated review.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import re
import sys
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.movie_metadata import MovieMetadata


LEGACY_COLUMNS = [
    "title",
    "vault_id",
    "imdb_rating",
    "rt_percent",
    "certificate",
    "franchise",
    "keywords",
    "director",
    "release_year",
    "genres",
    "awards",
    "runtime_min",
    "verified_year",
    "top_billed_actor",
    "top_3_actors",
    "plot_summary",
    "imdb_votes",
    "imdb_id",
    "tmdb_id",
    "digital_location",
    "poster_url",
]

STAGED_COLUMNS = [
    "vault_id",
    "title",
    "year",
    "verified_year",
    "runtime_min",
    "imdb_rating",
    "imdb_votes",
    "rt_score",
    "imdb_id",
    "tmdb_id",
    "certificate",
    "franchise",
    "keywords",
    "genres",
    "director",
    "top_billed_actor",
    "top_3_actors",
    "awards",
    "plot",
    "digital_location",
    "poster_url",
]

INTEGER_FIELDS = {
    "release_year",
    "verified_year",
    "runtime_min",
    "imdb_votes",
    "tmdb_id",
    "rt_percent",
}
FLOAT_FIELDS = {"imdb_rating"}
NULL_TOKENS = {"", "nan", "none", "null", "n/a", "na"}
GENRE_SEPARATOR_RE = re.compile(r"[|;,]")
SPACE_RE = re.compile(r"\s+")


class LegacyCsvError(ValueError):
    """Raised when the legacy CSV cannot be staged safely."""


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.casefold() in NULL_TOKENS:
        return None
    return text


def normalize_integer(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def normalize_float(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number


def split_genres(value: Any) -> list[str]:
    text = clean_text(value)
    if text is None:
        return []

    genres: list[str] = []
    seen: set[str] = set()
    for raw_token in GENRE_SEPARATOR_RE.split(text):
        token = clean_text(raw_token)
        if token is None:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        genres.append(token)
    return genres


def normalize_imdb_id(value: Any) -> str | None:
    text = clean_text(value)
    return text.casefold() if text is not None else None


def normalize_legacy_row(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Map one legacy row to the canonical staged representation."""

    metadata = MovieMetadata.from_mapping(raw)
    return {
        "vault_id": clean_text(raw.get("vault_id")),
        "title": metadata.title or None,
        "year": metadata.year,
        "verified_year": normalize_integer(raw.get("verified_year")),
        "runtime_min": metadata.runtime,
        "imdb_rating": metadata.imdb_rating,
        "imdb_votes": metadata.imdb_votes,
        "rt_score": metadata.rt_score,
        "imdb_id": metadata.imdb_id,
        "tmdb_id": metadata.tmdb_id,
        "certificate": clean_text(raw.get("certificate")),
        "franchise": metadata.collection,
        "keywords": clean_text(raw.get("keywords")),
        "genres": metadata.genres,
        "director": clean_text(raw.get("director")),
        "top_billed_actor": clean_text(raw.get("top_billed_actor")),
        "top_3_actors": clean_text(raw.get("top_3_actors")),
        "awards": metadata.awards,
        "plot": metadata.plot,
        "digital_location": "; ".join(metadata.where_to_watch) or None,
        "poster_url": metadata.poster_url,
    }


def _normalized_title(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "").strip()).casefold()


def _record_reference(row_number: int, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row": row_number,
        "vault_id": row.get("vault_id"),
        "title": row.get("title"),
        "year": row.get("year"),
        "imdb_id": row.get("imdb_id"),
        "tmdb_id": row.get("tmdb_id"),
    }


def _duplicate_issues(
    rows: Sequence[Mapping[str, Any]], field: str, issue_type: str
) -> list[dict[str, Any]]:
    matches: dict[Any, list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        value = row.get(field)
        if value is not None:
            matches[value].append((row_number, row))

    issues = []
    for value, entries in sorted(matches.items(), key=lambda item: str(item[0])):
        if len(entries) < 2:
            continue
        identities = {(_normalized_title(row.get("title")), row.get("year")) for _, row in entries}
        issues.append(
            {
                "type": issue_type,
                "field": field,
                "value": value,
                "rows": [row_number for row_number, _ in entries],
                "conflicting_title_year": len(identities) > 1,
                "records": [_record_reference(row_number, row) for row_number, row in entries],
            }
        )
    return issues


def _title_year_issues(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    matches: dict[str, list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    for row_number, row in enumerate(rows, start=2):
        title_key = _normalized_title(row.get("title"))
        if title_key:
            matches[title_key].append((row_number, row))

    issues = []
    for title_key, entries in sorted(matches.items()):
        years = sorted({row.get("year") for _, row in entries if row.get("year") is not None})
        if len(years) < 2:
            continue
        issues.append(
            {
                "type": "title_year_conflict",
                "normalized_title": title_key,
                "years": years,
                "rows": [row_number for row_number, _ in entries],
                "records": [_record_reference(row_number, row) for row_number, row in entries],
            }
        )
    return issues


def _normalization_issues(
    raw_rows: Sequence[Mapping[str, Any]], staged_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row_number, (raw, staged) in enumerate(zip(raw_rows, staged_rows), start=2):
        if staged.get("title") is None:
            issues.append({"type": "missing_title", "row": row_number})
        for field in sorted(INTEGER_FIELDS | FLOAT_FIELDS):
            source = clean_text(raw.get(field))
            staged_field = {
                "release_year": "year",
                "rt_percent": "rt_score",
            }.get(field, field)
            if source is not None and staged.get(staged_field) is None:
                issues.append(
                    {
                        "type": "invalid_numeric_value",
                        "row": row_number,
                        "field": field,
                        "value": source,
                    }
                )
    return issues


TITLE_YEAR_RE = re.compile(r"\((\d{4})\)\s*$")


def _year_issues(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        year = row.get("year")
        verified_year = row.get("verified_year")
        title = str(row.get("title") or "")
        match = TITLE_YEAR_RE.search(title)
        embedded_year = int(match.group(1)) if match else None

        if year is None and verified_year is None:
            issues.append(
                {
                    "type": "missing_year",
                    **_record_reference(row_number, row),
                }
            )
        if year is not None and verified_year is not None and year != verified_year:
            issues.append(
                {
                    "type": "verified_year_conflict",
                    "row": row_number,
                    "release_year": year,
                    "verified_year": verified_year,
                    "record": _record_reference(row_number, row),
                }
            )
        if embedded_year is not None and year is not None and embedded_year != year:
            issues.append(
                {
                    "type": "title_embedded_year_conflict",
                    "row": row_number,
                    "embedded_year": embedded_year,
                    "release_year": year,
                    "record": _record_reference(row_number, row),
                }
            )
    return issues


def build_review_report(
    raw_rows: Sequence[Mapping[str, Any]],
    staged_rows: Sequence[Mapping[str, Any]],
    *,
    input_path: pathlib.Path | None = None,
    output_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    issues = [
        *_normalization_issues(raw_rows, staged_rows),
        *_duplicate_issues(staged_rows, "imdb_id", "duplicate_imdb_id"),
        *_duplicate_issues(staged_rows, "tmdb_id", "duplicate_tmdb_id"),
        *_title_year_issues(staged_rows),
        *_year_issues(staged_rows),
    ]
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        counts[str(issue["type"])] += 1

    return {
        "schema_version": 1,
        "source": {
            "path": str(input_path) if input_path is not None else None,
            "row_count": len(raw_rows),
            "column_count": len(LEGACY_COLUMNS),
        },
        "staged": {
            "path": str(output_path) if output_path is not None else None,
            "row_count": len(staged_rows),
            "columns": STAGED_COLUMNS,
        },
        "summary": {
            "issue_count": len(issues),
            "issue_counts": dict(sorted(counts.items())),
            "requires_review": bool(issues),
        },
        "issues": issues,
    }


def read_legacy_csv(path: pathlib.Path) -> list[dict[str, str | None]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LegacyCsvError("legacy CSV is missing a header row")
        fieldnames = [name.strip() for name in reader.fieldnames]
        if fieldnames != LEGACY_COLUMNS:
            missing = [name for name in LEGACY_COLUMNS if name not in fieldnames]
            unexpected = [name for name in fieldnames if name not in LEGACY_COLUMNS]
            raise LegacyCsvError(
                "legacy CSV must use the exact 21-column header "
                f"(missing={missing}, unexpected={unexpected}, order_matches=False)"
            )

        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise LegacyCsvError(f"row {row_number} has more than 21 columns")
            rows.append({key: value for key, value in row.items()})
        return rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else value


def write_staged_csv(path: pathlib.Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STAGED_COLUMNS, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STAGED_COLUMNS})


def prepare_legacy_vault_csv(
    input_path: pathlib.Path,
    output_path: pathlib.Path,
    report_path: pathlib.Path,
) -> dict[str, Any]:
    resolved_paths = {input_path.resolve(), output_path.resolve(), report_path.resolve()}
    if len(resolved_paths) != 3:
        raise LegacyCsvError("input, staged output, and review report paths must be different")

    raw_rows = read_legacy_csv(input_path)
    staged_rows = [normalize_legacy_row(row) for row in raw_rows]
    report = build_review_report(
        raw_rows,
        staged_rows,
        input_path=input_path,
        output_path=output_path,
    )

    write_staged_csv(output_path, staged_rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage a legacy 21-column Vault CSV and emit a JSON review report."
    )
    parser.add_argument("--input", required=True, type=pathlib.Path, help="Legacy CSV path.")
    parser.add_argument("--output", required=True, type=pathlib.Path, help="Staged CSV path.")
    parser.add_argument(
        "--report",
        required=True,
        type=pathlib.Path,
        help="Machine-readable JSON review report path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = prepare_legacy_vault_csv(args.input, args.output, args.report)
    except (OSError, LegacyCsvError) as exc:
        raise SystemExit(f"Unable to stage legacy CSV: {exc}") from exc

    print(
        f"Staged {report['staged']['row_count']} rows; "
        f"review issues: {report['summary']['issue_count']}"
    )
    print(f"Staged CSV: {args.output}")
    print(f"Review report: {args.report}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
