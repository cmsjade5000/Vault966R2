from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import httpx
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.movie import Movie
from api.utils.omdb import extract_rotten_tomatoes_score, parse_imdb_rating, parse_imdb_votes
from api.utils.providers import merge_providers
from core.movie_metadata import MovieMetadata


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


def _extract_us_certificate(detail: Dict) -> Optional[str]:
    release_dates = detail.get("release_dates", {}) or {}
    for country in release_dates.get("results", []) or []:
        if country.get("iso_3166_1") != "US":
            continue
        for release in country.get("release_dates", []) or []:
            certificate = str(release.get("certification") or "").strip()
            if certificate:
                return certificate
    return None


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

    imdb_rating = parse_imdb_rating(omdb_data.get("imdbRating"))
    if imdb_rating is not None:
        candidate["imdb_rating"] = imdb_rating

    imdb_votes = parse_imdb_votes(omdb_data.get("imdbVotes"))
    if imdb_votes is not None:
        candidate["imdb_votes"] = imdb_votes

    rt_score = extract_rotten_tomatoes_score(omdb_data)
    if rt_score is not None:
        candidate["rt_score"] = rt_score

    rated = omdb_data.get("Rated")
    if rated and rated != "N/A":
        candidate["certificate"] = rated

    candidate["last_omdb_fetch_at"] = datetime.now(timezone.utc)
    candidate["omdb_payload_sha"] = _payload_sha(omdb_data)


def _payload_sha(payload: Dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


ROMAN_NUMERALS = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "v": "5",
    "vi": "6",
    "vii": "7",
    "viii": "8",
    "ix": "9",
    "x": "10",
}


def _clean_title_aliases(title: str) -> str:
    import re

    cleaned = title.strip()
    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.replace("&", "and")
    cleaned = re.sub(
        r"\bpart\s+([ivx]+)\b",
        lambda m: f"part {ROMAN_NUMERALS.get(m.group(1).lower(), m.group(1))}",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def iter_tmdb_search_variants(title: str, year: int | None) -> List[Tuple[str, Optional[int], str]]:
    """Generate search retries for TMDb when a strict title+year match fails."""

    variants: List[Tuple[str, Optional[int], str]] = []
    base = title.strip()
    cleaned = _clean_title_aliases(base)
    for query, tag in ((base, "exact"), (cleaned, "alias_cleaned")):
        variants.append((query, year, tag))
        if year is not None:
            for delta in (1, -1, 2, -2):
                variants.append((query, year + delta, f"{tag}_year_{delta:+d}"))
        variants.append((query, None, f"{tag}_title_only"))

    # Dedupe by (query, year)
    seen: set[Tuple[str, Optional[int]]] = set()
    deduped: List[Tuple[str, Optional[int], str]] = []
    for query, yr, tag in variants:
        key = (query.lower().strip(), yr)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((query, yr, tag))
    return deduped


def _compute_match_confidence(
    requested_title: str,
    requested_year: int | None,
    matched_title: str,
    matched_year: int | None,
    strategy: str,
) -> float:
    import difflib

    def norm(value: str) -> str:
        return _clean_title_aliases(value).lower()

    ratio = difflib.SequenceMatcher(a=norm(requested_title), b=norm(matched_title)).ratio()
    year_bonus = 0.0
    if requested_year is not None and matched_year is not None:
        delta = abs(requested_year - matched_year)
        year_bonus = 0.15 if delta == 0 else 0.08 if delta == 1 else 0.03 if delta == 2 else -0.08
    penalty = 0.08 if "title_only" in strategy else 0.0
    confidence = max(0.0, min(1.0, ratio + year_bonus - penalty))
    return float(round(confidence, 3))


def lookup_movie_candidates(title: str, year: int | None = None, limit: int = 5) -> List[dict]:
    api_key = settings.tmdb_api_key
    if not api_key:
        raise MovieLookupUnavailable("TMDb API key not configured")

    identifiers: tuple[int, ...] = ()
    match_strategy = "exact"
    for query, yr, strategy in iter_tmdb_search_variants(title, year):
        identifiers = _tmdb_search_ids(api_key, query, yr)
        if identifiers:
            match_strategy = strategy
            break
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
            "certificate": _extract_us_certificate(detail),
            "matched_tmdb_title": detail.get("title") or detail.get("name") or "",
            "matched_tmdb_year": release_year,
            "match_strategy": match_strategy,
            "last_tmdb_fetch_at": datetime.now(timezone.utc),
            "tmdb_payload_sha": _payload_sha(detail),
        }
        candidate["match_confidence"] = _compute_match_confidence(
            title,
            year,
            candidate["matched_tmdb_title"] or candidate["title"],
            release_year,
            match_strategy,
        )

        if omdb_key and imdb_id:
            try:
                omdb_payload = _omdb_details(omdb_key, imdb_id)
            except MovieLookupError:
                omdb_payload = None
            _enrich_with_omdb(candidate, omdb_payload)

        normalized = MovieMetadata.from_mapping(candidate).to_lookup_dict()
        normalized.update(
            {
                "matched_tmdb_title": candidate["matched_tmdb_title"],
                "matched_tmdb_year": candidate["matched_tmdb_year"],
                "match_strategy": candidate["match_strategy"],
                "match_confidence": candidate["match_confidence"],
            }
        )
        results.append(normalized)

    if not results:
        raise MovieLookupNotFound("No TMDb results found")

    return results


def lookup_local_candidates(
    db: Session,
    title: str,
    year: int | None = None,
    limit: int = 5,
    exclude_id: int | None = None,
) -> List[dict]:
    search_title = title.strip()
    if not search_title:
        return []

    def tokenize(value: str) -> List[str]:
        import re

        tokens = re.split(r"[^a-zA-Z0-9]+", value.lower())
        return [token for token in tokens if len(token) > 2]

    tokens = tokenize(search_title)
    query = db.query(Movie).options(selectinload(Movie.genres))
    if exclude_id is not None:
        query = query.filter(Movie.id != exclude_id)
    if tokens:
        conditions = [func.lower(Movie.title).like(f"%{token}%") for token in tokens]
        query = query.filter(or_(*conditions))
    else:
        query = query.filter(Movie.title.ilike(f"%{search_title}%"))
    if year is not None:
        query = query.filter(Movie.year.between(year - 2, year + 2))

    candidates = query.limit(max(limit * 5, 20)).all()
    if not candidates:
        return []

    scored = []
    for movie in candidates:
        confidence = _compute_match_confidence(
            search_title,
            year,
            movie.title or "",
            movie.year,
            "vault",
        )
        scored.append((confidence, movie))
    scored.sort(key=lambda item: item[0], reverse=True)

    results: List[dict] = []
    for confidence, movie in scored[:limit]:
        genres = [genre.name for genre in movie.genres] if movie.genres else []
        results.append(
            {
                "title": movie.title or "",
                "year": movie.year,
                "runtime": movie.runtime,
                "synopsis": movie.plot or "",
                "overview": movie.plot or "",
                "tmdb_id": movie.tmdb_id,
                "imdb_id": movie.imdb_id,
                "poster_url": movie.poster_url,
                "backdrop_url": movie.backdrop_url,
                "genres": genres,
                "source": "vault",
                "vault_id": movie.id,
                "vault_label": movie.vault_id,
                "match_confidence": confidence,
            }
        )

    return results


def lookup_movie(title: str, year: int | None = None) -> dict:
    """Fetch metadata for a movie using TMDb search and detail endpoints."""

    candidates = lookup_movie_candidates(title, year, limit=1)
    metadata = dict(candidates[0])
    metadata.setdefault("genres", [])
    metadata.setdefault("where_to_watch", [])
    return metadata
