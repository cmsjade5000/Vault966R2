"""Remove provider tags from the database and/or enriched CSV exports."""

from __future__ import annotations

import argparse
import csv
import pathlib
import shutil
import sys
from datetime import datetime, timezone
from typing import Dict, Iterable

from sqlalchemy import or_

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402

PROVIDER_COLUMNS = (
    "watch_region",
    "providers_stream",
    "providers_rent",
    "providers_buy",
    "tmdb_watch_url",
    "where_to_watch",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear provider tags from DB/CSV.")
    parser.add_argument(
        "--db",
        action="store_true",
        help="Clear where_to_watch in the database.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Clear provider columns in an enriched CSV.",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="CSV to scrub (default: newest enriched_movies*.csv in data/).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: data/<input>_no_providers_<stamp>.csv).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input CSV (writes via temp file).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing changes.",
    )
    return parser.parse_args()


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


def read_csv(path: pathlib.Path) -> tuple[list[str], list[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, [dict(row) for row in reader]


def write_csv(
    path: pathlib.Path, fieldnames: Iterable[str], rows: Iterable[Dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def scrub_csv(path: pathlib.Path, *, output: pathlib.Path, in_place: bool, dry_run: bool) -> int:
    fieldnames, rows = read_csv(path)
    if not fieldnames:
        raise SystemExit(f"CSV appears to have no header: {path}")
    for column in PROVIDER_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    updated = 0
    for row in rows:
        touched = False
        for column in PROVIDER_COLUMNS:
            if row.get(column):
                row[column] = ""
                touched = True
        if touched:
            updated += 1
    if dry_run:
        return updated
    if in_place:
        temp_path = output.with_suffix(output.suffix + ".tmp")
        write_csv(temp_path, fieldnames, rows)
        shutil.move(str(temp_path), str(output))
    else:
        write_csv(output, fieldnames, rows)
    return updated


def scrub_db(dry_run: bool) -> int:
    with SessionLocal() as session:
        query = session.query(Movie).filter(
            or_(
                Movie.where_to_watch.isnot(None),
                Movie.where_to_watch != "",
            )
        )
        if dry_run:
            return query.count()
        updated = query.update({Movie.where_to_watch: None}, synchronize_session=False)
        session.commit()
        return int(updated or 0)


def main() -> int:
    args = parse_args()
    do_db = args.db
    do_csv = args.csv
    if not do_db and not do_csv:
        do_db = True
        do_csv = True

    if do_db:
        cleared = scrub_db(args.dry_run)
        action = "Would clear" if args.dry_run else "Cleared"
        print(f"{action} where_to_watch for {cleared} movies in the database.")

    if do_csv:
        input_path = pathlib.Path(args.input) if args.input else _latest_enriched_csv()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        default_output = DATA_DIR / f"{input_path.stem}_no_providers_{stamp}.csv"
        output_path = input_path if args.in_place else pathlib.Path(args.output or default_output)
        cleared = scrub_csv(
            input_path, output=output_path, in_place=args.in_place, dry_run=args.dry_run
        )
        action = "Would clear" if args.dry_run else "Cleared"
        print(f"{action} provider columns for {cleared} rows.")
        if not args.dry_run:
            print(f"Wrote: {output_path}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
