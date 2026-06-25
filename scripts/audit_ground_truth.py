"""Compare a ground-truth title/year CSV against the database movie table.

Related skill: `database-health-check`.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Iterable, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.config import settings  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: F401,E402 - ensure mapper registration

DEFAULT_GROUND_TRUTH = ROOT / "data" / "ground_truth_titles.csv"
DEFAULT_REPORTS = ROOT / "reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit ground-truth titles/years against the DB")
    parser.add_argument(
        "--ground-truth",
        default=str(DEFAULT_GROUND_TRUTH),
        help="Path to ground-truth CSV (default: data/ground_truth_titles.csv)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional SQLAlchemy database URL override (defaults to settings DATABASE_URL)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_REPORTS),
        help="Directory for CSV reports (default: reports/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max rows to print per category (default: 20). Use 0 to suppress output.",
    )
    return parser.parse_args()


def _normalize_title(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _parse_year(value: Any) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _load_ground_truth(path: pathlib.Path) -> list[tuple[str, Optional[int]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = list(handle)
    if not lines:
        raise ValueError("ground truth CSV is empty")

    header_index = None
    for index, raw_line in enumerate(lines):
        if not raw_line.strip():
            continue
        parsed = next(csv.reader([raw_line]))
        normalized = [name.strip().lower() for name in parsed if name]
        if "title" in normalized:
            header_index = index
            break
    if header_index is None:
        raise ValueError("ground truth CSV is missing a header row")

    reader = csv.DictReader(lines[header_index:])
    if not reader.fieldnames:
        raise ValueError("ground truth CSV is missing a header row")
    fieldnames = {name.strip().lower() for name in reader.fieldnames if name}
    if "title" not in fieldnames or "year" not in fieldnames:
        raise ValueError("ground truth CSV must include 'title' and 'year' columns")

    rows: list[tuple[str, Optional[int]]] = []
    for row in reader:
        lowered = {str(key).strip().lower(): value for key, value in row.items() if key}
        title = _normalize_title(lowered.get("title"))
        if not title:
            continue
        year = _parse_year(lowered.get("year"))
        rows.append((title, year))
    return rows


def _load_db_movies(db: Session) -> list[tuple[str, Optional[int], int]]:
    rows = db.query(Movie.id, Movie.title, Movie.year).all()
    normalized: list[tuple[str, Optional[int], int]] = []
    for movie_id, title, year in rows:
        normalized.append((_normalize_title(title), year, int(movie_id)))
    return normalized


def _write_csv(
    path: pathlib.Path, fieldnames: Iterable[str], rows: Iterable[dict[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _sample(label: str, rows: list[dict[str, Any]], *, limit: int) -> None:
    if limit == 0:
        return
    print(f"{label}: {len(rows)}")
    for row in rows[:limit]:
        print(f"  - {row}")


def main() -> int:
    args = parse_args()
    ground_truth_path = pathlib.Path(args.ground_truth)
    if not ground_truth_path.exists():
        raise SystemExit(f"Ground truth CSV not found: {ground_truth_path}")

    ground_truth = _load_ground_truth(ground_truth_path)
    ground_truth_counts = Counter(ground_truth)

    db_url = args.database_url or settings.database_url or "sqlite:///./vault.db"
    engine = create_engine(db_url, future=True)
    with Session(engine) as db:
        db_rows = _load_db_movies(db)

    db_keys = [(title, year) for title, year, _ in db_rows]
    db_counts = Counter(db_keys)
    db_ids_by_key: dict[tuple[str, Optional[int]], list[int]] = defaultdict(list)
    for title, year, movie_id in db_rows:
        db_ids_by_key[(title, year)].append(movie_id)

    ground_truth_set = set(ground_truth_counts)
    db_set = set(db_counts)

    missing = sorted(ground_truth_set - db_set)
    extra = sorted(db_set - ground_truth_set)

    missing_rows = [{"title": title, "year": year or ""} for title, year in missing]
    extra_rows = [
        {
            "title": title,
            "year": year or "",
            "movie_ids": "; ".join(map(str, db_ids_by_key[(title, year)])),
        }
        for title, year in extra
    ]

    duplicate_rows: list[dict[str, Any]] = []
    for key, count in ground_truth_counts.items():
        if count > 1:
            duplicate_rows.append(
                {
                    "source": "ground_truth",
                    "title": key[0],
                    "year": key[1] or "",
                    "count": count,
                    "movie_ids": "",
                }
            )
    for key, count in db_counts.items():
        if count > 1:
            duplicate_rows.append(
                {
                    "source": "db",
                    "title": key[0],
                    "year": key[1] or "",
                    "count": count,
                    "movie_ids": "; ".join(map(str, db_ids_by_key[key])),
                }
            )

    output_dir = pathlib.Path(args.output_dir)
    _write_csv(output_dir / "ground_truth_missing.csv", ["title", "year"], missing_rows)
    _write_csv(output_dir / "ground_truth_extra.csv", ["title", "year", "movie_ids"], extra_rows)
    _write_csv(
        output_dir / "ground_truth_duplicates.csv",
        ["source", "title", "year", "count", "movie_ids"],
        duplicate_rows,
    )

    print(f"Ground truth rows: {len(ground_truth)} (unique: {len(ground_truth_set)})")
    print(f"DB rows: {len(db_keys)} (unique: {len(db_set)})")
    _sample("Missing in DB", missing_rows, limit=args.limit)
    _sample("Extra in DB", extra_rows, limit=args.limit)
    _sample("Duplicates", duplicate_rows, limit=args.limit)

    print(f"Wrote: {output_dir / 'ground_truth_missing.csv'}")
    print(f"Wrote: {output_dir / 'ground_truth_extra.csv'}")
    print(f"Wrote: {output_dir / 'ground_truth_duplicates.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
