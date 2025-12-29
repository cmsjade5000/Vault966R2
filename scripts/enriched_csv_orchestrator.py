"""Run TMDb enrichment, CSV audit, and OMDb backfill in a single pipeline.

Related skills: `csv-import-guard`, `movie-import-review`.

Defaults to the most recently modified enriched_movies*.csv in data/.
Outputs are timestamped to avoid overwriting existing files.
"""

from __future__ import annotations

import argparse
import pathlib
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orchestrate CSV audit + API backfills")
    parser.add_argument(
        "--input",
        default=None,
        help="CSV to process (default: most recent enriched_movies*.csv in data/).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Final CSV output path (default: data/<input>_backfilled_<stamp>.csv).",
    )
    parser.add_argument(
        "--region",
        default="US",
        help="Region code for TMDb providers + audit output (default: US).",
    )
    parser.add_argument(
        "--skip-tmdb",
        action="store_true",
        help="Skip TMDb enrichment step (use input CSV directly).",
    )
    parser.add_argument(
        "--skip-omdb",
        action="store_true",
        help="Skip OMDb ratings backfill step.",
    )
    parser.add_argument(
        "--stamp",
        default=None,
        help="Override timestamp suffix (default: UTC now).",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Skip importing the final CSV into the database.",
    )
    return parser.parse_args()


def _format_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def _run(cmd: list[str]) -> None:
    print(f"$ {_format_cmd(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


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


def main() -> int:
    args = parse_args()
    input_path = pathlib.Path(args.input) if args.input else _latest_enriched_csv()
    if not input_path.exists():
        raise SystemExit(f"Input CSV not found: {input_path}")

    stamp = args.stamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    base_name = input_path.stem

    tmdb_output = DATA_DIR / f"{base_name}_tmdb_{stamp}.csv"
    normalized_output = DATA_DIR / f"{base_name}_normalized_{stamp}.csv"
    needs_review_output = DATA_DIR / f"{base_name}_needs_review_{stamp}.csv"
    quarantine_output = DATA_DIR / f"{base_name}_quarantine_{stamp}.csv"
    final_output = (
        pathlib.Path(args.output)
        if args.output
        else DATA_DIR / f"{base_name}_backfilled_{stamp}.csv"
    )

    source_csv = input_path
    if not args.skip_tmdb:
        tmdb_script = ROOT / "legacy" / "etl" / "enrich_tmdb.py"
        _run(
            [
                sys.executable,
                str(tmdb_script),
                "--output",
                str(tmdb_output),
                "--v2",
                "--allow-missing-tmdb",
                "--country",
                args.region,
            ]
        )
        source_csv = tmdb_output

    review_script = ROOT / "scripts" / "enriched_csv_review.py"
    _run(
        [
            sys.executable,
            str(review_script),
            "--input",
            str(source_csv),
            "--output",
            str(normalized_output),
            "--needs-review",
            str(needs_review_output),
            "--quarantine",
            str(quarantine_output),
            "--region",
            args.region,
        ]
    )

    if args.skip_omdb:
        if normalized_output != final_output:
            shutil.copy2(normalized_output, final_output)
    else:
        omdb_script = ROOT / "scripts" / "fill_missing_ratings_csv.py"
        _run(
            [
                sys.executable,
                str(omdb_script),
                "--input",
                str(normalized_output),
                "--output",
                str(final_output),
            ]
        )

    if not args.skip_import:
        import_script = ROOT / "scripts" / "import_latest_enriched_csv.py"
        _run([sys.executable, str(import_script), "--input", str(final_output)])

    print("Done.")
    print(f"Input: {input_path}")
    if not args.skip_tmdb:
        print(f"TMDb: {tmdb_output}")
    print(f"Audit normalized: {normalized_output}")
    print(f"Needs review: {needs_review_output}")
    print(f"Quarantine: {quarantine_output}")
    print(f"Final: {final_output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
