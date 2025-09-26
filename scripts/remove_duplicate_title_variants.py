"""Identify and optionally remove duplicate movies with year-suffix titles.

Some imports create placeholder records such as "Footloose (1984)" alongside
the canonical "Footloose" entry. These suffix variants often lack TMDb data, so
they never receive poster URLs or enrichment. This helper groups movies by a
sanitized title (trailing "(YYYY)" removed) and year, keeps the best candidate
per group, and reports or deletes the remaining placeholders.

Dry run:
    python scripts/remove_duplicate_title_variants.py

Apply deletions:
    python scripts/remove_duplicate_title_variants.py --delete
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: E402,F401  # ensure mapper registration

YEAR_SUFFIX_RE = re.compile(r"^(?P<base>.+)\s\((?P<year>\d{4})\)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean title/year duplicate rows")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete flagged duplicates instead of printing only",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of groups shown",
    )
    return parser.parse_args()


def sanitize_title(title: str) -> str:
    match = YEAR_SUFFIX_RE.match(title.strip())
    if match:
        return match.group("base").strip()
    return title.strip()


def has_year_suffix(movie: Movie) -> bool:
    return YEAR_SUFFIX_RE.match(movie.title.strip()) is not None


def score_candidate(movie: Movie) -> Tuple[int, int, int, int, int]:
    return (
        1 if has_year_suffix(movie) else 0,
        0 if movie.tmdb_id is not None else 1,
        0 if movie.imdb_id else 1,
        0 if movie.poster_url else 1,
        movie.id,
    )


def collect_groups(movies: Iterable[Movie]) -> Dict[Tuple[str, int], List[Movie]]:
    grouped: Dict[Tuple[str, int], List[Movie]] = defaultdict(list)
    for movie in movies:
        base_title = sanitize_title(movie.title).lower()
        key = (base_title, movie.year or 0)
        grouped[key].append(movie)
    return grouped


def describe_movie(movie: Movie) -> str:
    return (
        f"id={movie.id} title='{movie.title}' year={movie.year} "
        f"imdb={movie.imdb_id or '-'} tmdb={movie.tmdb_id or '-'}"
    )


def main() -> int:
    args = parse_args()

    with SessionLocal() as session:
        movies = session.execute(select(Movie)).scalars().all()

        groups = collect_groups(movies)
        flagged: List[Tuple[Movie, List[Movie]]] = []

        for key, entries in groups.items():
            if len(entries) < 2:
                continue

            sorted_entries = sorted(entries, key=score_candidate)
            keeper = sorted_entries[0]

            duplicates = [item for item in sorted_entries[1:] if item.tmdb_id is None]
            if not duplicates:
                continue

            flagged.append((keeper, duplicates))

        if not flagged:
            print("No duplicate title/year rows detected.")
            return 0

        total = len(flagged)
        limited = flagged[: args.limit] if args.limit is not None else flagged

        print(f"Found {total} duplicate title/year groups (showing {len(limited)}):")
        for keeper, duplicates in limited:
            base = sanitize_title(keeper.title)
            print(f"\nBase title: '{base}' (keeping {describe_movie(keeper)})")
            for dup in duplicates:
                print(f"  - remove {describe_movie(dup)}")

        if not args.delete:
            print("\nDry run complete. Re-run with --delete to apply removals.")
            return 0

        delete_ids = [dup.id for _, duplicates in flagged for dup in duplicates]
        if not delete_ids:
            print("No rows matched deletion criteria.")
            return 0

        session.query(Movie).filter(Movie.id.in_(delete_ids)).delete(synchronize_session=False)
        session.commit()
        print(f"Deleted {len(delete_ids)} rows.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
