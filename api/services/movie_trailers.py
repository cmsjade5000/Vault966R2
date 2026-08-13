from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from api.config import settings
from api.models.movie import Movie
from api.utils.provider_errors import format_provider_error

TMDB_API_BASE = "https://api.themoviedb.org/3"
YOUTUBE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{6,128}$")
MISSING_TRAILER_RECHECK_AFTER = timedelta(days=30)


class MovieTrailerError(Exception):
    """Base exception for trailer lookups."""


class MovieTrailerUnavailable(MovieTrailerError):
    """Raised when trailer lookup cannot reach the external provider."""


class MovieTrailerNotFound(MovieTrailerError):
    """Raised when a movie has no playable trailer."""


@dataclass(frozen=True)
class MovieTrailer:
    site: str
    key: str
    name: str | None
    url: str

    @property
    def embed_url(self) -> str:
        return f"https://www.youtube-nocookie.com/embed/{self.key}"


def _clean_text(value: object | None, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


def _youtube_trailer_from_movie(movie: Movie) -> MovieTrailer | None:
    if movie.trailer_site != "youtube" or not movie.trailer_key:
        return None
    if not YOUTUBE_KEY_RE.fullmatch(movie.trailer_key):
        return None
    return MovieTrailer(
        site="youtube",
        key=movie.trailer_key,
        name=movie.trailer_name,
        url=movie.trailer_url or f"https://www.youtube.com/watch?v={movie.trailer_key}",
    )


def _video_score(item: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
    video_type = str(item.get("type") or "").strip().lower()
    site = str(item.get("site") or "").strip().lower()
    language = str(item.get("iso_639_1") or "").strip().lower()
    country = str(item.get("iso_3166_1") or "").strip().upper()
    official = item.get("official") is True
    published_at = str(item.get("published_at") or "")

    return (
        1 if site == "youtube" else 0,
        3 if video_type == "trailer" else 1 if video_type == "teaser" else 0,
        1 if official else 0,
        1 if language == "en" else 0,
        1 if country in {"US", ""} else 0,
        published_at,
    )


def select_tmdb_trailer(payload: dict[str, Any]) -> MovieTrailer | None:
    results = payload.get("results")
    if not isinstance(results, list):
        return None

    candidates: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        site = str(item.get("site") or "").strip().lower()
        video_type = str(item.get("type") or "").strip().lower()
        key = str(item.get("key") or "").strip()
        if site != "youtube" or video_type != "trailer":
            continue
        if not YOUTUBE_KEY_RE.fullmatch(key):
            continue
        candidates.append(item)

    if not candidates:
        return None

    selected = max(candidates, key=_video_score)
    key = str(selected["key"]).strip()
    return MovieTrailer(
        site="youtube",
        key=key,
        name=_clean_text(selected.get("name"), 300),
        url=f"https://www.youtube.com/watch?v={key}",
    )


def _fetch_tmdb_videos(tmdb_id: int) -> dict[str, Any]:
    api_key = settings.tmdb_api_key
    if not api_key:
        raise MovieTrailerUnavailable("TMDb trailer lookup is not configured")
    provider_error: MovieTrailerUnavailable | None = None
    try:
        response = httpx.get(
            f"{TMDB_API_BASE}/movie/{tmdb_id}/videos",
            params={"api_key": api_key},
            timeout=8.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        provider_error = MovieTrailerUnavailable(
            format_provider_error("TMDb trailer lookup failed", exc)
        )
    if provider_error is not None:
        raise provider_error from None
    return response.json()


def _recently_checked(value: datetime | None) -> bool:
    if value is None:
        return False
    checked_at = value
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - checked_at < MISSING_TRAILER_RECHECK_AFTER


def get_or_fetch_movie_trailer(db: Session, movie_id: int) -> MovieTrailer:
    movie = db.query(Movie).filter(Movie.id == movie_id).one_or_none()
    if movie is None:
        raise MovieTrailerNotFound("Movie not found")

    cached = _youtube_trailer_from_movie(movie)
    if cached is not None:
        return cached
    if movie.trailer_checked_at is not None and _recently_checked(movie.trailer_checked_at):
        raise MovieTrailerNotFound("Trailer not available")

    if not movie.tmdb_id:
        movie.trailer_checked_at = datetime.now(timezone.utc)
        db.add(movie)
        db.commit()
        raise MovieTrailerNotFound("Trailer not available")

    payload = _fetch_tmdb_videos(movie.tmdb_id)
    trailer = select_tmdb_trailer(payload)
    movie.trailer_checked_at = datetime.now(timezone.utc)
    if trailer is None:
        movie.trailer_site = None
        movie.trailer_key = None
        movie.trailer_name = None
        movie.trailer_url = None
        db.add(movie)
        db.commit()
        raise MovieTrailerNotFound("Trailer not available")

    movie.trailer_site = trailer.site
    movie.trailer_key = trailer.key
    movie.trailer_name = trailer.name
    movie.trailer_url = trailer.url
    db.add(movie)
    db.commit()
    logging.getLogger(__name__).info("Cached trailer for movie_id=%s", movie_id)
    return trailer


def get_cached_movie_trailer(db: Session, movie_id: int) -> MovieTrailer:
    movie = db.query(Movie).filter(Movie.id == movie_id).one_or_none()
    if movie is None:
        raise MovieTrailerNotFound("Movie not found")

    cached = _youtube_trailer_from_movie(movie)
    if cached is None:
        raise MovieTrailerNotFound("Trailer not available")
    return cached
