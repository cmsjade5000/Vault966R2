"""Normalize enriched movies CSV and produce a review/quarantine queue.

Related skills: `csv-import-guard`, `movie-import-review`.

This script is intentionally offline (no API calls). It helps catch obvious data
quality issues before the CSV is ingested, and produces a small "needs review"
file you can patch via manual overrides.

Example:
  python scripts/enriched_csv_review.py \\
    --input data/enriched_movies.csv \\
    --output data/enriched_movies_v2.csv \\
    --needs-review data/enriched_movies_needs_review.csv \\
    --quarantine data/enriched_movies_quarantine.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.enriched_csv import (  # noqa: E402
    countries_display_from_iso,
    is_blank,
    join_csv_tokens,
    languages_display_from_iso,
    normalize_countries,
    normalize_languages,
    normalize_where_to_watch,
    parse_int,
    parse_iso_date,
    split_csv_tokens,
)


DEFAULT_COLUMNS = [
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

# Contract: enriched_movies.csv must include these columns and pass validate_enriched_contract.
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

ENRICHED_CSV_OPTIONAL_COLUMNS = [
    "where_to_watch",
    "languages_iso",
    "countries_iso",
]

ENRICHED_CSV_WATCH_COLUMNS = [
    "watch_region",
    "providers_stream",
    "providers_rent",
    "providers_buy",
    "tmdb_watch_url",
]


IMDB_ID_RE = re.compile(r"^tt\d{7,9}$", re.IGNORECASE)
ISO2_RE = re.compile(r"^[A-Za-z]{2}$")
YEAR_MIN = 1870
YEAR_MAX = 2100


V2_EXTRA_COLUMNS = [
    "matched_tmdb_title",
    "matched_tmdb_year",
    "match_confidence",
    "match_strategy",
    "watch_region",
    "providers_stream",
    "providers_rent",
    "providers_buy",
    "tmdb_watch_url",
    "languages_iso",
    "countries_iso",
    "languages_display",
    "countries_display",
    "quality_flags",
    "quality_quarantined",
]


@dataclass(frozen=True)
class GateConfig:
    min_runtime: int = 40
    region: str = "US"
    min_mainstream_votes: int = 2000


@dataclass(frozen=True)
class QualityRule:
    key: str
    description: str
    predicate: Callable[[Dict[str, Any], GateConfig], bool]


class EnrichedCsvContractError(ValueError):
    """Raised when enriched_movies.csv violates required contract invariants."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize enriched CSV + build review queue")
    parser.add_argument(
        "--input",
        default=str(ROOT / "data" / "enriched_movies.csv"),
        help="Path to the input CSV (default: data/enriched_movies.csv)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "enriched_movies_v2.csv"),
        help="Path to the normalized output CSV (default: data/enriched_movies_v2.csv)",
    )
    parser.add_argument(
        "--needs-review",
        default=str(ROOT / "data" / "enriched_movies_needs_review.csv"),
        help="Path to write needs-review CSV (default: data/enriched_movies_needs_review.csv)",
    )
    parser.add_argument(
        "--quarantine",
        default=str(ROOT / "data" / "enriched_movies_quarantine.csv"),
        help="Path to write quarantined rows (default: data/enriched_movies_quarantine.csv)",
    )
    parser.add_argument(
        "--region",
        default="US",
        help="Region for watch providers (default: US). Used for URL selection and output metadata.",
    )
    parser.add_argument(
        "--min-runtime",
        type=int,
        default=40,
        help="Quarantine rows with runtime below this (default: 40).",
    )
    parser.add_argument(
        "--min-mainstream-votes",
        type=int,
        default=2000,
        help="Quarantine rows with implausibly low IMDb votes for mainstream titles (default: 2000).",
    )
    parser.add_argument(
        "--apply-overrides",
        default=None,
        help="Optional needs-review CSV with override_* columns to apply before gating.",
    )
    return parser.parse_args()


def _strip_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _parse_float(value: Any) -> float | None:
    text = _strip_value(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


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


def _validate_iso_tokens(value: Any, field: str, row_number: int) -> None:
    tokens = split_csv_tokens(_strip_value(value))
    for token in tokens:
        if not ISO2_RE.match(token):
            raise EnrichedCsvContractError(
                f"Row {row_number}: {field} has non-ISO2 token '{token}'"
            )


def _validate_numeric_field(
    value: Any,
    field: str,
    row_number: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> None:
    text = _strip_value(value)
    if not text:
        return
    parsed = parse_int(text)
    if parsed is None:
        raise EnrichedCsvContractError(f"Row {row_number}: {field} is not an integer")
    if min_value is not None and parsed < min_value:
        raise EnrichedCsvContractError(f"Row {row_number}: {field} below {min_value}")
    if max_value is not None and parsed > max_value:
        raise EnrichedCsvContractError(f"Row {row_number}: {field} above {max_value}")


def validate_enriched_header(fieldnames: list[str]) -> None:
    missing = [col for col in ENRICHED_CSV_REQUIRED_COLUMNS if col not in fieldnames]

    has_watch = all(col in fieldnames for col in ENRICHED_CSV_WATCH_COLUMNS)
    has_any_watch = any(col in fieldnames for col in ENRICHED_CSV_WATCH_COLUMNS)
    has_legacy_watch = "where_to_watch" in fieldnames
    if not has_watch and has_legacy_watch:
        missing = [col for col in missing if col not in ENRICHED_CSV_WATCH_COLUMNS]

    if missing:
        raise EnrichedCsvContractError(f"Missing required columns: {', '.join(missing)}")
    if has_any_watch and not has_watch:
        raise EnrichedCsvContractError(
            "Partial watch provider columns present; expected "
            + ", ".join(ENRICHED_CSV_WATCH_COLUMNS)
        )
    if not has_watch and not has_legacy_watch:
        raise EnrichedCsvContractError(
            "Missing watch providers; expected provider columns or legacy where_to_watch"
        )


def validate_enriched_row(row: Dict[str, Any], row_number: int) -> None:
    title = _strip_value(row.get("title"))
    if not title:
        raise EnrichedCsvContractError(f"Row {row_number}: missing title")

    year_raw = _strip_value(row.get("year"))
    imdb_id = _strip_value(row.get("imdb_id"))
    tmdb_id = _strip_value(row.get("tmdb_id"))

    if not year_raw and not imdb_id and not tmdb_id:
        raise EnrichedCsvContractError(
            f"Row {row_number}: missing year/imdb_id/tmdb_id for identification"
        )
    if year_raw and not _is_valid_year(year_raw):
        raise EnrichedCsvContractError(f"Row {row_number}: invalid year '{year_raw}'")
    if imdb_id and not IMDB_ID_RE.match(imdb_id):
        raise EnrichedCsvContractError(f"Row {row_number}: invalid imdb_id '{imdb_id}'")
    if tmdb_id and not tmdb_id.isdigit():
        raise EnrichedCsvContractError(f"Row {row_number}: invalid tmdb_id '{tmdb_id}'")

    watch_region = _strip_value(row.get("watch_region"))
    if watch_region and not _is_valid_iso2(watch_region):
        raise EnrichedCsvContractError(f"Row {row_number}: invalid watch_region '{watch_region}'")

    _validate_numeric_field(row.get("runtime_min"), "runtime_min", row_number, min_value=1)
    _validate_numeric_field(row.get("imdb_votes"), "imdb_votes", row_number, min_value=0)
    _validate_numeric_field(row.get("rt_score"), "rt_score", row_number, min_value=0, max_value=100)

    rating = _parse_float(row.get("imdb_rating"))
    if _strip_value(row.get("imdb_rating")) and (rating is None or not (0.0 <= rating <= 10.0)):
        raise EnrichedCsvContractError(f"Row {row_number}: invalid imdb_rating")

    scraped = _strip_value(row.get("tmdb_last_scraped"))
    if scraped and parse_iso_date(scraped) is None:
        raise EnrichedCsvContractError(f"Row {row_number}: invalid tmdb_last_scraped '{scraped}'")

    if _strip_value(row.get("languages_iso")):
        _validate_iso_tokens(row.get("languages_iso"), "languages_iso", row_number)
    if _strip_value(row.get("countries_iso")):
        _validate_iso_tokens(row.get("countries_iso"), "countries_iso", row_number)


def validate_enriched_contract(fieldnames: list[str], rows: list[Dict[str, Any]]) -> None:
    validate_enriched_header(fieldnames)
    for idx, row in enumerate(rows, start=2):
        validate_enriched_row(row, idx)


def _row_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (str(row.get("title") or "").strip().lower(), str(row.get("year") or "").strip())


def _is_mainstream(row: Dict[str, Any]) -> bool:
    genres = str(row.get("genres") or "").lower()
    # Heuristic: if it looks like a short, treat as not-mainstream.
    title = str(row.get("title") or "").lower()
    if "short" in title:
        return False
    if "documentary" in genres:
        # lots of docs are popular, but treat as not-mainstream for vote-floor checks.
        return False
    rating = row.get("imdb_rating")
    try:
        rating_f = float(str(rating)) if rating not in (None, "") else None
    except ValueError:
        rating_f = None
    runtime = parse_int(row.get("runtime_min"))
    year = parse_int(row.get("year"))
    if rating_f is not None and rating_f >= 6.5:
        return True
    if runtime is not None and runtime >= 70 and year is not None and year >= 1970:
        return True
    return False


def _runtime_too_short(row: Dict[str, Any], config: GateConfig) -> bool:
    runtime = parse_int(row.get("runtime_min"))
    return runtime is not None and runtime < config.min_runtime


def _missing_tmdb_last_scraped(row: Dict[str, Any], config: GateConfig) -> bool:
    return parse_iso_date(str(row.get("tmdb_last_scraped") or "")) is None


def _imdb_votes_implausibly_low(row: Dict[str, Any], config: GateConfig) -> bool:
    votes = parse_int(row.get("imdb_votes"))
    return votes is not None and votes < config.min_mainstream_votes and _is_mainstream(row)


def _languages_unmapped(row: Dict[str, Any], config: GateConfig) -> bool:
    languages = normalize_languages(str(row.get("languages") or ""))
    return bool(languages.unmapped)


def _countries_unmapped(row: Dict[str, Any], config: GateConfig) -> bool:
    countries = normalize_countries(str(row.get("countries") or ""))
    return bool(countries.unmapped) and not countries.iso


QUALITY_RULES = [
    QualityRule(
        key="runtime_too_short",
        description="Runtime is below the minimum threshold.",
        predicate=_runtime_too_short,
    ),
    QualityRule(
        key="missing_poster",
        description="Poster URL is missing.",
        predicate=lambda row, config: is_blank(row.get("poster_url")),
    ),
    QualityRule(
        key="missing_backdrop",
        description="Backdrop URL is missing.",
        predicate=lambda row, config: is_blank(row.get("backdrop_url")),
    ),
    QualityRule(
        key="missing_tmdb_last_scraped",
        description="TMDb scrape timestamp is missing or invalid.",
        predicate=_missing_tmdb_last_scraped,
    ),
    QualityRule(
        key="imdb_votes_implausibly_low",
        description="IMDb votes are implausibly low for a mainstream title.",
        predicate=_imdb_votes_implausibly_low,
    ),
    QualityRule(
        key="languages_unmapped",
        description="Languages could not be mapped to ISO codes.",
        predicate=_languages_unmapped,
    ),
    QualityRule(
        key="countries_unmapped",
        description="Countries could not be mapped to ISO codes.",
        predicate=_countries_unmapped,
    ),
]


def quality_flags(row: Dict[str, Any], config: GateConfig) -> list[str]:
    flags: list[str] = []
    for rule in QUALITY_RULES:
        if rule.predicate(row, config):
            flags.append(rule.key)
    return flags


def normalize_row(row: Dict[str, Any], config: GateConfig) -> Dict[str, Any]:
    normalized = dict(row)
    for col in DEFAULT_COLUMNS:
        normalized.setdefault(col, "")

    legacy_watch = str(normalized.get("where_to_watch") or "")
    has_provider_columns = any(
        str(normalized.get(column) or "").strip()
        for column in ("providers_stream", "providers_rent", "providers_buy")
    )
    if has_provider_columns:
        normalized["watch_region"] = str(normalized.get("watch_region") or config.region).upper()
        normalized["providers_stream"] = str(normalized.get("providers_stream") or "")
        normalized["providers_rent"] = str(normalized.get("providers_rent") or "")
        normalized["providers_buy"] = str(normalized.get("providers_buy") or "")
        normalized["tmdb_watch_url"] = str(normalized.get("tmdb_watch_url") or "")
    else:
        watch = normalize_where_to_watch(legacy_watch, region=config.region)
        normalized["watch_region"] = config.region.upper()
        normalized["providers_stream"] = join_csv_tokens(watch.stream)
        normalized["providers_rent"] = join_csv_tokens(watch.rent)
        normalized["providers_buy"] = join_csv_tokens(watch.buy)
        normalized["tmdb_watch_url"] = watch.tmdb_watch_url or ""
    normalized.pop("where_to_watch", None)

    langs = normalize_languages(str(normalized.get("languages") or ""))
    normalized["languages_iso"] = join_csv_tokens(langs.iso)
    normalized["languages"] = join_csv_tokens(langs.iso)
    normalized["languages_display"] = join_csv_tokens(
        languages_display_from_iso(langs.iso) or langs.display
    )

    ctries = normalize_countries(str(normalized.get("countries") or ""))
    normalized["countries_iso"] = join_csv_tokens(ctries.iso)
    normalized["countries"] = join_csv_tokens(ctries.iso)
    normalized["countries_display"] = join_csv_tokens(
        countries_display_from_iso(ctries.iso) or ctries.display
    )

    flags = quality_flags(normalized, config)
    normalized["quality_flags"] = "; ".join(flags)
    normalized["quality_quarantined"] = "true" if flags else "false"

    return normalized


def needs_review_row(row: Dict[str, Any], *, flags: Iterable[str]) -> Dict[str, Any]:
    return {
        "title": row.get("title", ""),
        "year": row.get("year", ""),
        "imdb_id": row.get("imdb_id", ""),
        "tmdb_id": row.get("tmdb_id", ""),
        "reasons": "; ".join(flags),
        "suggested_fix": "Edit override_* fields and re-run (or re-enrich if missing IDs).",
        "override_title": "",
        "override_year": "",
        "override_runtime_min": "",
        "override_poster_url": "",
        "override_backdrop_url": "",
        "override_tmdb_last_scraped": "",
        "override_imdb_rating": "",
        "override_imdb_votes": "",
    }


def write_csv(path: pathlib.Path, fieldnames: list[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_csv(path: pathlib.Path) -> tuple[list[str], list[Dict[str, Any]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, [dict(row) for row in reader]


def apply_overrides(rows: list[Dict[str, Any]], overrides_path: pathlib.Path) -> int:
    """Apply override_* columns from a needs-review CSV to input rows."""

    _, overrides = load_csv(overrides_path)
    if not overrides:
        return 0

    by_key: dict[Tuple[str, str], Dict[str, Any]] = {}
    for override in overrides:
        key = _row_key(override)
        if key != ("", ""):
            by_key[key] = override

    applied = 0
    for row in rows:
        key = _row_key(row)
        override = by_key.get(key)
        if not override:
            continue

        changed = False
        for field, override_field in (
            ("title", "override_title"),
            ("year", "override_year"),
            ("runtime_min", "override_runtime_min"),
            ("poster_url", "override_poster_url"),
            ("backdrop_url", "override_backdrop_url"),
            ("tmdb_last_scraped", "override_tmdb_last_scraped"),
            ("imdb_rating", "override_imdb_rating"),
            ("imdb_votes", "override_imdb_votes"),
        ):
            value = str(override.get(override_field) or "").strip()
            if not value:
                continue
            row[field] = value
            changed = True

        if changed:
            applied += 1

    return applied


def main() -> int:
    args = parse_args()
    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    config = GateConfig(
        min_runtime=args.min_runtime,
        region=args.region,
        min_mainstream_votes=args.min_mainstream_votes,
    )

    input_fieldnames, rows = load_csv(input_path)
    if args.apply_overrides:
        overrides_path = pathlib.Path(args.apply_overrides)
        applied = apply_overrides(rows, overrides_path)
        print(f"Applied overrides: {applied} from {overrides_path}")

    try:
        validate_enriched_contract(input_fieldnames, rows)
    except EnrichedCsvContractError as exc:
        raise SystemExit(f"Enriched CSV contract violation: {exc}") from exc

    normalized_rows: list[Dict[str, Any]] = []
    quarantined_rows: list[Dict[str, Any]] = []
    review_rows: list[Dict[str, Any]] = []

    for row in rows:
        normalized = normalize_row(row, config)
        flags = [
            flag for flag in str(normalized.get("quality_flags") or "").split(";") if flag.strip()
        ]
        if flags:
            quarantined_rows.append(normalized)
            review_rows.append(needs_review_row(normalized, flags=flags))
        else:
            normalized_rows.append(normalized)

    output_path = pathlib.Path(args.output)
    quarantine_path = pathlib.Path(args.quarantine)
    needs_review_path = pathlib.Path(args.needs_review)

    out_fieldnames: list[str] = []
    for name in [*input_fieldnames, *DEFAULT_COLUMNS, *V2_EXTRA_COLUMNS]:
        if name and name not in out_fieldnames:
            out_fieldnames.append(name)
    out_fieldnames = [name for name in out_fieldnames if name != "where_to_watch"]

    write_csv(output_path, out_fieldnames, normalized_rows)
    write_csv(quarantine_path, out_fieldnames, quarantined_rows)
    write_csv(
        needs_review_path,
        [
            "title",
            "year",
            "imdb_id",
            "tmdb_id",
            "reasons",
            "suggested_fix",
            "override_title",
            "override_year",
            "override_runtime_min",
            "override_poster_url",
            "override_backdrop_url",
            "override_tmdb_last_scraped",
            "override_imdb_rating",
            "override_imdb_votes",
        ],
        review_rows,
    )

    print(
        f"Normalized: {len(normalized_rows)} | quarantined: {len(quarantined_rows)} | needs review: {len(review_rows)}"
    )
    print(f"Wrote: {output_path}")
    print(f"Wrote: {quarantine_path}")
    print(f"Wrote: {needs_review_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
