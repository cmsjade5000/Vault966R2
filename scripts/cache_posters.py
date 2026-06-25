#!/usr/bin/env python3
"""Download validated TMDB movie posters into Vault966's local cache."""

from __future__ import annotations

import argparse
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.services.poster_cache import (  # noqa: E402
    ALLOWED_POSTER_SIZES,
    POSTER_CACHE_DIR,
    cache_stem,
    cached_poster_path,
    download_poster,
    poster_source_url,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache movie posters locally")
    parser.add_argument(
        "--sizes",
        default="w185,w342",
        help="Comma-separated poster sizes (default: w185,w342).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Concurrent downloads (default: 6, maximum: 8).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum movies to process (default: all).",
    )
    return parser.parse_args()


def _selected_sizes(raw: str) -> list[str]:
    sizes = [value.strip() for value in raw.split(",") if value.strip()]
    if not sizes or any(size not in ALLOWED_POSTER_SIZES for size in sizes):
        allowed = ", ".join(sorted(ALLOWED_POSTER_SIZES))
        raise ValueError(f"Sizes must be selected from: {allowed}")
    return list(dict.fromkeys(sizes))


def _poster_rows(limit: int) -> list[tuple[int, str]]:
    with SessionLocal() as db:
        query = (
            db.query(Movie.id, Movie.poster_url)
            .filter(
                Movie.poster_url.isnot(None),
                Movie.poster_url != "",
                Movie.poster_url != "N/A",
            )
            .order_by(Movie.id.asc())
        )
        if limit > 0:
            query = query.limit(limit)
        return [(movie_id, poster_url) for movie_id, poster_url in query.all()]


def build_jobs(
    rows: list[tuple[int, str]],
    sizes: list[str],
    cache_dir: pathlib.Path,
) -> tuple[list[tuple[str, str]], int, int]:
    jobs: list[tuple[str, str]] = []
    cached = 0
    unsupported = 0
    for movie_id, poster_url in rows:
        for size in sizes:
            try:
                source_url = poster_source_url(poster_url, size)
            except ValueError:
                unsupported += 1
                continue
            stem = cache_stem(movie_id, size, source_url)
            if cached_poster_path(cache_dir, stem):
                cached += 1
                continue
            jobs.append((source_url, stem))
    return jobs, cached, unsupported


def cache_posters(
    jobs: list[tuple[str, str]],
    cache_dir: pathlib.Path,
    workers: int,
) -> tuple[int, int]:
    completed = 0
    failed = 0
    timeout = httpx.Timeout(15.0, connect=4.0)
    limits = httpx.Limits(max_connections=workers, max_keepalive_connections=workers)
    with httpx.Client(timeout=timeout, limits=limits) as client:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    download_poster,
                    source_url,
                    cache_dir,
                    stem,
                    client=client,
                ): stem
                for source_url, stem in jobs
            }
            for index, future in enumerate(as_completed(futures), start=1):
                try:
                    future.result()
                    completed += 1
                except (httpx.HTTPError, OSError, ValueError):
                    failed += 1
                if index % 100 == 0 or index == len(futures):
                    print(
                        f"processed={index}/{len(futures)} "
                        f"downloaded={completed} failed={failed}",
                        flush=True,
                    )
    return completed, failed


def main() -> int:
    args = parse_args()
    try:
        sizes = _selected_sizes(args.sizes)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    workers = max(1, min(args.workers, 8))
    rows = _poster_rows(max(0, args.limit))
    jobs, cached, unsupported = build_jobs(rows, sizes, POSTER_CACHE_DIR)
    print(
        f"movies={len(rows)} sizes={','.join(sizes)} queued={len(jobs)} "
        f"cached={cached} unsupported={unsupported}",
        flush=True,
    )
    downloaded, failed = cache_posters(jobs, POSTER_CACHE_DIR, workers)
    print(
        f"complete downloaded={downloaded} cached={cached} "
        f"unsupported={unsupported} failed={failed}",
        flush=True,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
