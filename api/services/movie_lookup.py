from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional, Sequence

import httpx

from api.config import settings
from api.utils.providers import merge_providers


class MovieLookupError(Exception):
    """Raised when no matching movie could be found."""


class MovieLookupNotFound(MovieLookupError):
    """Raised when the lookup completed successfully but returned no items."""


class MovieLookupUnavailable(Exception):
    """Raised when lookup prerequisites (e.g., API keys) are missing."""


def _build_image_url(path: str | None, size: str) -> str | None:
    if not path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{path}"


def _extract_image_path(detail: Dict, primary_key: str, fallback_key: str) -> str | None:
    path = detail.get(primary_key)
    if path:
        return path

    images = detail.get("images")
    if isinstance(images, dict):
        items = images.get(fallback_key) or []
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict):
                    file_path = entry.get("file_path")
                    if file_path:
                        return file_path
    return None


def _extract_keywords(detail: Dict) -> List[str]:
    section = detail.get("keywords")
    candidates: Sequence = []
    if isinstance(section, dict):
        candidates = section.get("keywords") or section.get("results") or []
    elif isinstance(section, list):
        candidates = section

    keywords: List[str] = []
    for item in candidates:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = item
        if not name:
            continue
        label = str(name).strip()
        if label and label not in keywords:
            keywords.append(label)
    return keywords


def _extract_watch_providers(detail: Dict, region: str = "US") -> List[str]:
    root = detail.get("watch/providers")
    if not isinstance(root, dict):
        return []

    results = root.get("results")
    if not isinstance(results, dict):
        return []

    region_data = None
    for candidate in (region.upper(), "US"):
        data = results.get(candidate)
        if isinstance(data, dict):
            region_data = data
            break

    if not region_data:
        return []

    collected: List[str] = []
    buckets = [
        ("flatrate", None),
        ("ads", None),
        ("free", None),
        ("rent", "rent"),
        ("buy", "buy"),
    ]
    for bucket, qualifier in buckets:
        entries = region_data.get(bucket)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("provider_name")
            if not name:
                continue
            label = str(name).strip()
            if not label:
                continue
            if qualifier in {"rent", "buy"}:
                label = f"{label} ({qualifier})"
            collected.append(label)

    return merge_providers(collected)


def _select_release_date(detail: Dict, region: str = "US") -> Optional[str]:
    release_dates = detail.get("release_dates")
    if isinstance(release_dates, dict):
        results = release_dates.get("results")
        if isinstance(results, list):
            for entry in results:
                if not isinstance(entry, dict):
                    continue
                code = entry.get("iso_3166_1")
                if code and code.upper() != region.upper():
                    continue
                dates = entry.get("release_dates")
                if not isinstance(dates, list):
                    continue
                best: Optional[str] = None
                for candidate in dates:
                    if not isinstance(candidate, dict):
                        continue
                    release_value = candidate.get("release_date")
                    if not release_value:
                        continue
                    normalized = str(release_value)[:10]
                    if normalized and (best is None or normalized < best):
                        best = normalized
                if best:
                    return best

    release_date = detail.get("release_date")
    if release_date:
        return str(release_date)[:10]
    return None


def _parse_release_year(release_date: str | None) -> Optional[int]:
    if not release_date:
        return None
    release_date = release_date.strip()
    if len(release_date) < 4 or not release_date[:4].isdigit():
        return None
    return int(release_date[:4])


@lru_cache(maxsize=128)
def _tmdb_search_ids(api_key: str, title: str, year: Optional[int]) -> tuple[int, ...]:
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
        return ()

    filtered = []
    if year is not None:
        for result in results:
            release_date = result.get("release_date") or ""
            release_year = _parse_release_year(release_date)
            if release_year is None or abs(release_year - year) <= 1:
                filtered.append(result)

    candidates = filtered or results
    candidates.sort(key=lambda item: item.get("popularity", 0) or 0, reverse=True)
    identifiers: List[int] = []
    for candidate in candidates:
        tmdb_id = candidate.get("id")
        if tmdb_id:
            identifiers.append(int(tmdb_id))

    return tuple(identifiers)


@lru_cache(maxsize=256)
def _tmdb_movie_detail(api_key: str, tmdb_id: int) -> Dict:
    detail_params = {
        "api_key": api_key,
        "append_to_response": "external_ids,release_dates,keywords,images,watch/providers",
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

    return detail_response.json()


@lru_cache(maxsize=256)
def _omdb_details(api_key: str, imdb_id: str) -> Optional[Dict]:
    params = {"apikey": api_key, "i": imdb_id}
    try:
        response = httpx.get("https://www.omdbapi.com/", params=params, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MovieLookupError(f"OMDb lookup failed: {exc}") from exc

    data = response.json()
    if not data or str(data.get("Response")) != "True":
        return None
    return data


def _enrich_with_omdb(candidate: Dict, omdb_data: Optional[Dict]) -> None:
    if not omdb_data:
        return

    plot = omdb_data.get("Plot")
    if plot and plot != "N/A":
        candidate["synopsis"] = plot
        candidate["overview"] = plot

    poster = omdb_data.get("Poster")
    if poster and poster != "N/A":
        candidate["poster_url"] = poster

    runtime_value = omdb_data.get("Runtime")
    if runtime_value and runtime_value != "N/A":
        try:
            runtime_int = int(str(runtime_value).split()[0])
        except (ValueError, TypeError):
            runtime_int = None
        if runtime_int:
            candidate["runtime"] = runtime_int


def lookup_movie_candidates(title: str, year: int | None = None, limit: int = 5) -> List[dict]:
    api_key = settings.tmdb_api_key
    if not api_key:
        raise MovieLookupUnavailable("TMDb API key not configured")

    identifiers = _tmdb_search_ids(api_key, title, year)
    if not identifiers:
        raise MovieLookupNotFound("No TMDb results found")

    results: List[dict] = []
    omdb_key = settings.omdb_api_key
    limit = max(1, limit)

    for tmdb_id in identifiers[:limit]:
        detail = _tmdb_movie_detail(api_key, tmdb_id)
        release_date = _select_release_date(detail)
        release_year = _parse_release_year(release_date)

        external_ids = detail.get("external_ids", {}) or {}
        imdb_id = external_ids.get("imdb_id") or None
        if imdb_id:
            imdb_id = imdb_id.strip() or None

        genres = [genre.get("name", "").strip() for genre in detail.get("genres", [])]
        genres = [name for name in genres if name]

        poster_path = _extract_image_path(detail, "poster_path", "posters")
        backdrop_path = _extract_image_path(detail, "backdrop_path", "backdrops")
        keywords = _extract_keywords(detail)
        providers = _extract_watch_providers(detail)

        candidate = {
            "title": detail.get("title") or detail.get("name") or title,
            "year": release_year,
            "runtime": detail.get("runtime"),
            "synopsis": detail.get("overview") or "",
            "overview": detail.get("overview") or "",
            "tmdb_id": tmdb_id,
            "imdb_id": imdb_id,
            "poster_url": _build_image_url(poster_path, "w342"),
            "backdrop_url": _build_image_url(backdrop_path, "w780"),
            "release_date": release_date,
            "genres": genres,
            "source": "tmdb",
            "where_to_watch": providers,
            "keywords": keywords,
        }

        if omdb_key and imdb_id:
            try:
                omdb_payload = _omdb_details(omdb_key, imdb_id)
            except MovieLookupError:
                omdb_payload = None
            _enrich_with_omdb(candidate, omdb_payload)

        results.append(candidate)

    if not results:
        raise MovieLookupNotFound("No TMDb results found")

    return results


def lookup_movie(title: str, year: int | None = None) -> dict:
    """Fetch metadata for a movie using TMDb search and detail endpoints."""

    candidates = lookup_movie_candidates(title, year, limit=1)
    metadata = dict(candidates[0])
    metadata.setdefault("genres", [])
    metadata.setdefault("where_to_watch", [])
    return metadata
