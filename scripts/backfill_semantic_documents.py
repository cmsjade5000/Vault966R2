"""Backfill semantic search documents and embeddings for movies."""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Role  # noqa: F401,E402  # ensure mapper registration
from api.services.semantic_search import (  # noqa: E402
    SemanticSearchError,
    SemanticSearchUnavailable,
    backfill_movie_documents,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill movie semantic search documents.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum movies to process (0 = all).",
    )
    parser.add_argument(
        "--after-id",
        type=int,
        default=0,
        help="Start after this movie ID (resume batches).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = args.limit or None
    after_id = args.after_id or None

    with SessionLocal() as db:
        if after_id is not None:
            ids_query = db.query(Movie.id).filter(Movie.id > after_id).order_by(Movie.id.asc())
        else:
            ids_query = db.query(Movie.id).order_by(Movie.id.asc())
        if limit:
            ids_query = ids_query.limit(limit)
        ids = [row[0] for row in ids_query.all() if row[0] is not None]
        if not ids:
            print("No movies found to process.")
            return 0

        try:
            created, updated = backfill_movie_documents(
                db,
                limit=limit,
                after_id=after_id,
            )
        except SemanticSearchUnavailable as exc:
            print(f"Semantic search unavailable: {exc}")
            return 1
        except SemanticSearchError as exc:
            print(f"Semantic search failed: {exc}")
            return 1

    last_id = ids[-1]
    print(f"created: {created}, updated: {updated}")
    if limit:
        print(f"resume with --after-id {last_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
