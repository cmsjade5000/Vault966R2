"""Import the most recent enriched_movies*.csv into the database.

Related skill: `csv-import-guard`.

Uses legacy/etl/etl_seed.py and defaults to the newest CSV in data/.
"""

from __future__ import annotations

import argparse
import pathlib
import shlex
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ETL_SCRIPT = ROOT / "legacy" / "etl" / "etl_seed.py"
POSTER_CACHE_SCRIPT = ROOT / "scripts" / "cache_posters.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the latest enriched CSV into the DB")
    parser.add_argument(
        "--input",
        default=None,
        help="CSV to import (default: newest enriched_movies*.csv in data/).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run importer without committing changes.",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        help="Disable network lookups for missing imdb_id.",
    )
    parser.add_argument(
        "--allow-tmdb-only",
        action="store_true",
        help="Allow inserts using tmdb_id when imdb_id cannot be resolved.",
    )
    parser.add_argument(
        "--encoding",
        default=None,
        help="CSV file encoding (default: importer default).",
    )
    return parser.parse_args()


def _latest_enriched_csv() -> pathlib.Path:
    if not DATA_DIR.exists():
        raise SystemExit(f"Data directory not found: {DATA_DIR}")
    candidates: list[pathlib.Path] = []
    for path in DATA_DIR.glob("enriched_movies*.csv"):
        name = path.name
        if "needs_review" in name or "quarantine" in name:
            continue
        if path.is_file():
            candidates.append(path)
    if not candidates:
        raise SystemExit("No enriched_movies*.csv found in data/.")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _format_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def main() -> int:
    args = parse_args()
    input_path = pathlib.Path(args.input) if args.input else _latest_enriched_csv()
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    cmd = [
        sys.executable,
        str(ETL_SCRIPT),
        "--path",
        str(input_path),
        "--format",
        "csv",
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.no_network:
        cmd.append("--no-network")
    if args.allow_tmdb_only:
        cmd.append("--allow-tmdb-only")
    if args.encoding:
        cmd.extend(["--encoding", args.encoding])

    print(f"$ {_format_cmd(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)
    if not args.dry_run:
        cache_cmd = [sys.executable, str(POSTER_CACHE_SCRIPT)]
        print(f"$ {_format_cmd(cache_cmd)}")
        subprocess.run(cache_cmd, check=True, cwd=ROOT)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
