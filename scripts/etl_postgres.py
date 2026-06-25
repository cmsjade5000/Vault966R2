"""Seed the Postgres database with the sample dataset."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT_DIR / "scripts" / "samples" / "movies.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Postgres with sample movies")
    parser.add_argument(
        "--path",
        default=str(SAMPLE_PATH),
        help="Path to a movies JSON/CSV file (default: scripts/samples/sample_movies.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run importer without committing changes.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        help="Optional explicit format override for the importer.",
    )
    args = parser.parse_args()

    cmd = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "etl_seed.py"),
        "--path",
        args.path,
    ]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.format:
        cmd.extend(["--format", args.format])

    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
