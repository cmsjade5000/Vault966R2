from __future__ import annotations

import threading

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role
from api.models.movie import Movie
from api.services.poster_cache import (
    POSTER_CACHE_DIR,
    cache_stem,
    cached_poster_path,
    download_poster,
    poster_media_type,
    poster_source_url,
)
from api.services.profiles import ROLE_ADMIN, ROLE_REVIEWER

router = APIRouter()

_cache_locks: dict[str, threading.Lock] = {}
_cache_locks_guard = threading.Lock()


def _lock_for(stem: str) -> threading.Lock:
    with _cache_locks_guard:
        return _cache_locks.setdefault(stem, threading.Lock())


@router.get("/ui/posters/{movie_id}/{size}", response_class=FileResponse)
def cached_movie_poster(
    movie_id: int,
    size: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> FileResponse:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    try:
        source_url = poster_source_url(movie.poster_url, size)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poster not available",
        ) from exc

    stem = cache_stem(movie_id, size, source_url)
    cached = cached_poster_path(POSTER_CACHE_DIR, stem)
    if cached is None:
        with _lock_for(stem):
            cached = cached_poster_path(POSTER_CACHE_DIR, stem)
            if cached is None:
                try:
                    cached = download_poster(source_url, POSTER_CACHE_DIR, stem)
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Poster temporarily unavailable",
                    ) from exc

    return FileResponse(
        cached,
        media_type=poster_media_type(cached),
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
