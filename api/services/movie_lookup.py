from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Optional

import httpx

from api.config import settings


class MovieLookupError(Exception):
    """Raised when no matching movie could be found."""


class MovieLookupUnavailable(Exception):
    """Raised when lookup prerequisites (e.g., API keys) are missing."""


def _build_image_url(path: str | None, size: str) -> str | None:
    if not path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{path}"


@lru_cache(maxsize=128)
def _lookup_movie_cached(api_key: str, title: str, year: Optional[int]) -> dict:
    params: dict[str, str | int] = {
        "api_key": api_key,
        "query": title,
        "include_adult": "false",
    }
    if year is not None:
        params["year"] = year

    try:
        search_response = httpx.get(
            "https://api.themoviedb.org/3/search/movie",
            params=params,
            timeout=10.0,
        )
        search_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MovieLookupError(f"TMDb search failed: {exc}") from exc

    results = search_response.json().get("results", [])
    if not results:
        raise MovieLookupError("No TMDb results found")

    filtered = []
    if year is not None:
        for result in results:
            release_date = (result.get("release_date") or "").strip()
            release_year = int(release_date[:4]) if release_date[:4].isdigit() else None
            if release_year is None or abs(release_year - year) <= 1:
                filtered.append(result)

    candidates = filtered or results
    candidates.sort(key=lambda item: item.get("popularity", 0) or 0, reverse=True)
    chosen = candidates[0]
    tmdb_id = chosen.get("id")
    if not tmdb_id:
        raise MovieLookupError("TMDb result missing identifier")

    detail_params = {
        "api_key": api_key,
        "append_to_response": "external_ids",
    }

    try:
        detail_response = httpx.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params=detail_params,
            timeout=10.0,
        )
        detail_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MovieLookupError(f"TMDb detail fetch failed: {exc}") from exc

    detail = detail_response.json()
    release_date = (detail.get("release_date") or "").strip()
    release_year = int(release_date[:4]) if release_date[:4].isdigit() else None

    genres = [genre.get("name", "").strip() for genre in detail.get("genres", [])]
    genres = [name for name in genres if name]

    external_ids = detail.get("external_ids", {}) or {}
    imdb_id = external_ids.get("imdb_id") or None
    if imdb_id:
        imdb_id = imdb_id.strip()

    metadata = {
        "title": detail.get("title") or detail.get("name") or title,
        "year": release_year,
        "runtime": detail.get("runtime"),
        "overview": detail.get("overview") or "",
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "poster_url": _build_image_url(detail.get("poster_path"), "w500"),
        "backdrop_url": _build_image_url(detail.get("backdrop_path"), "w780"),
        "release_date": release_date or None,
        "genres": genres,
        "source": "tmdb",
        "where_to_watch": [],
    }

    return metadata


def lookup_movie(title: str, year: int | None = None) -> dict:
    """Fetch metadata for a movie using TMDb search and detail endpoints."""

    api_key = settings.tmdb_api_key
    if not api_key:
        raise MovieLookupUnavailable("TMDb API key not configured")

    cached = _lookup_movie_cached(api_key, title, year)
    metadata = deepcopy(cached)
    metadata["genres"] = list(metadata.get("genres", []))
    metadata["where_to_watch"] = list(metadata.get("where_to_watch", []))
    return metadata
