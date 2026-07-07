from __future__ import annotations

import logging
import math
import re
from functools import lru_cache
from typing import List, Optional, Tuple

import httpx
from sqlalchemy import func
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.movie import Genre, Mood, Movie
from api.models.person import Person, Role
from api.schemas.movie_detail import (
    MovieDetail,
    PersonNested,
    RoleWithPersonRead,
    SimilarMovie,
    TopBilledEntry,
)
from core.poster_theme import select_poster_theme
from core.genres import split_and_normalize
from api.utils.providers import split_providers
from core.enriched_csv import (
    countries_display_from_iso,
    languages_display_from_iso,
    normalize_countries,
    normalize_languages,
)

TMDB_API_BASE = "https://api.themoviedb.org/3"
YOUTUBE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{6,128}$")


@lru_cache(maxsize=256)
def _tmdb_related_ids(api_key: str, tmdb_id: int, endpoint: str) -> tuple[int, ...]:
    params = {"api_key": api_key}
    try:
        response = httpx.get(
            f"{TMDB_API_BASE}/movie/{tmdb_id}/{endpoint}", params=params, timeout=8.0
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger = logging.getLogger(__name__)
        logger.warning("TMDb %s fetch failed for %s: %s", endpoint, tmdb_id, exc)
        return ()

    payload = response.json()
    results = payload.get("results")
    if not isinstance(results, list):
        return ()

    tmdb_ids: list[int] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        candidate = item.get("id")
        if isinstance(candidate, int):
            tmdb_ids.append(candidate)
        elif isinstance(candidate, str) and candidate.isdigit():
            tmdb_ids.append(int(candidate))

    return tuple(tmdb_ids)


def _get_tmdb_similar(db: Session, movie: Movie, limit: int = 12) -> List[SimilarMovie]:
    api_key = settings.tmdb_api_key
    if not api_key or not movie.tmdb_id:
        return []

    recommended = list(_tmdb_related_ids(api_key, movie.tmdb_id, "recommendations"))
    similar = list(_tmdb_related_ids(api_key, movie.tmdb_id, "similar"))
    ordered_tmdb_ids: list[int] = []
    seen_ids: set[int] = set()
    for candidate in recommended + similar:
        if candidate not in seen_ids:
            seen_ids.add(candidate)
            ordered_tmdb_ids.append(candidate)
        if len(ordered_tmdb_ids) >= limit * 2:
            break

    if not ordered_tmdb_ids:
        return []

    matches = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.tmdb_id.in_(ordered_tmdb_ids))
        .all()
    )
    movie_by_tmdb_id = {candidate.tmdb_id: candidate for candidate in matches if candidate.tmdb_id}

    resolved: list[SimilarMovie] = []
    for tmdb_id in ordered_tmdb_ids:
        candidate = movie_by_tmdb_id.get(tmdb_id)
        if candidate is None or candidate.id == movie.id:
            continue
        candidate_genres = _extract_genre_labels(candidate)
        resolved.append(
            SimilarMovie(
                id=candidate.id,
                title=candidate.title,
                poster_url=candidate.poster_url,
                year=candidate.year,
                flic_score=None,
                poster_theme=select_poster_theme(candidate_genres),
                genres=candidate_genres,
                imdb_rating=candidate.imdb_rating,
                rt_score=candidate.rt_score,
            )
        )
        if len(resolved) >= limit:
            break

    return resolved


def _fetch_movie(db: Session, movie_id: int) -> Optional[Movie]:
    base_query = db.query(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.moods),
    )
    try:
        return (
            base_query.options(selectinload(Movie.roles).selectinload(Role.person))
            .filter(Movie.id == movie_id)
            .one_or_none()
        )
    except (LookupError, ValueError, StatementError) as exc:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to load roles for movie_id=%s: %s", movie_id, exc)
        movie = base_query.filter(Movie.id == movie_id).one_or_none()
        if movie is not None:
            try:
                movie.roles = []
            except Exception:
                pass
        return movie


def _build_roles(movie: Movie) -> List[RoleWithPersonRead]:
    roles_with_person = []
    for role in movie.roles:
        person: Optional[Person] = role.person
        if person is None:
            continue
        role_type = role.role_type
        if hasattr(role_type, "value"):
            role_type_value = role_type.value
        elif role_type is None:
            role_type_value = ""
        else:
            role_type_value = str(role_type)
        roles_with_person.append(
            RoleWithPersonRead(
                id=role.id,
                movie_id=role.movie_id,
                person_id=role.person_id,
                role_type=role_type_value,
                character_name=role.character_name,
                billing_order=role.billing_order,
                person=PersonNested(
                    id=person.id,
                    name=person.name,
                    imdb_id=getattr(person, "imdb_id", None),
                    tmdb_id=getattr(person, "tmdb_id", None),
                ),
            )
        )
    roles_with_person.sort(
        key=lambda r: (
            r.billing_order is None,
            r.billing_order if r.billing_order is not None else math.inf,
            (r.person.name or "").lower(),
            r.person.id or 0,
        )
    )
    return roles_with_person


def _extract_genre_labels(movie: Movie) -> list[str]:
    try:
        raw = [getattr(genre, "name", None) for genre in movie.genres]
    except TypeError:
        raw = []
    return split_and_normalize([label for label in raw if label])


def _extract_mood_labels(movie: Movie) -> list[str]:
    try:
        raw = [getattr(mood, "name", None) for mood in movie.moods]
    except TypeError:
        raw = []
    cleaned: list[str] = []
    for label in raw:
        if not label:
            continue
        text = str(label).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _get_similarity_candidates(db: Session, movie: Movie) -> List[Movie]:
    genre_names = _extract_genre_labels(movie)
    mood_names = _extract_mood_labels(movie)
    base_year = _coerce_int(movie.year)

    query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    query = query.filter(Movie.id != movie.id)

    if genre_names:
        query = query.filter(Movie.genres.any(Genre.name.in_(genre_names)))
    elif mood_names:
        query = query.filter(Movie.moods.any(Mood.name.in_(mood_names)))
    elif base_year is not None:
        query = query.filter(Movie.year.between(base_year - 8, base_year + 8))

    return query.limit(300).all()


def _coerce_int(value: object | None) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    text = str(value).strip()
    if not text or not text.lstrip("-").isdigit():
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _score_similar(movie: Movie, candidates: List[Movie]) -> List[SimilarMovie]:
    base_genre_labels = _extract_genre_labels(movie)
    base_mood_labels = _extract_mood_labels(movie)
    base_genres = {label.lower() for label in base_genre_labels}
    base_moods = {label.lower() for label in base_mood_labels}
    base_year = _coerce_int(movie.year)
    base_runtime = _coerce_int(movie.runtime)

    scored: list[tuple[float, int, int, int, int, SimilarMovie]] = []
    for candidate in candidates:
        candidate_genre_labels = _extract_genre_labels(candidate)
        candidate_mood_labels = _extract_mood_labels(candidate)
        candidate_genres = {label.lower() for label in candidate_genre_labels}
        candidate_moods = {label.lower() for label in candidate_mood_labels}
        shared_genres = len(base_genres & candidate_genres)
        shared_moods = len(base_moods & candidate_moods)
        if (base_genres or base_moods) and shared_genres < 1 and shared_moods < 1:
            continue

        score = 0.0
        if shared_genres:
            score += shared_genres * 16
        if shared_moods:
            score += shared_moods * 10

        candidate_year = _coerce_int(candidate.year)
        year_delta = abs(base_year - candidate_year) if base_year and candidate_year else 999
        if year_delta != 999:
            score += max(0.0, 10.0 - min(year_delta, 10))

        candidate_runtime = _coerce_int(candidate.runtime)
        runtime_delta = (
            abs(base_runtime - candidate_runtime) if base_runtime and candidate_runtime else 999
        )
        if runtime_delta != 999:
            score += max(0.0, 8.0 - min(runtime_delta / 10.0, 8.0))

        scored.append(
            (
                score,
                shared_genres,
                shared_moods,
                -year_delta,
                -runtime_delta,
                SimilarMovie(
                    id=candidate.id,
                    title=candidate.title,
                    poster_url=candidate.poster_url,
                    year=candidate.year,
                    flic_score=round(score, 2),
                    poster_theme=select_poster_theme(candidate_genre_labels),
                    genres=candidate_genre_labels,
                    imdb_rating=candidate.imdb_rating,
                    rt_score=candidate.rt_score,
                ),
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3],
            item[4],
            item[5].id or 0,
        ),
        reverse=True,
    )

    if not scored:
        fallback = sorted(
            candidates,
            key=lambda c: (c.year or 0, c.id),
            reverse=True,
        )[:12]
        return [
            SimilarMovie(
                id=candidate.id,
                title=candidate.title,
                poster_url=candidate.poster_url,
                year=candidate.year,
                flic_score=None,
                poster_theme=select_poster_theme(_extract_genre_labels(candidate)),
                genres=_extract_genre_labels(candidate),
                imdb_rating=candidate.imdb_rating,
                rt_score=candidate.rt_score,
            )
            for candidate in fallback
        ]

    return [item[-1] for item in scored[:12]]


def _normalize_collection_key(value: object | None) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\b(collection|franchise|series|saga)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _infer_collection_for_title(db: Session, movie: Movie) -> str | None:
    title_key = _normalize_collection_key(movie.title)
    if not title_key:
        return None

    rows = (
        db.query(Movie.collection, func.count(Movie.id))
        .filter(Movie.collection.isnot(None))
        .filter(func.trim(Movie.collection) != "")
        .group_by(Movie.collection)
        .having(func.count(Movie.id) > 0)
        .all()
    )
    matches = [
        (collection.strip(), count)
        for collection, count in rows
        if collection and _normalize_collection_key(collection) == title_key
    ]
    if not matches:
        return None

    matches.sort(key=lambda item: (-int(item[1]), item[0].lower()))
    return matches[0][0]


def _collection_lineup_source(db: Session, movie: Movie) -> str | None:
    collection = (movie.collection or "").strip()
    if collection:
        return collection
    return _infer_collection_for_title(db, movie)


def _get_collection_lineup(
    db: Session, movie: Movie, limit: int = 12
) -> tuple[str | None, List[SimilarMovie]]:
    collection = _collection_lineup_source(db, movie)
    if not collection:
        return None, []

    candidates = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.id != movie.id)
        .filter(Movie.collection == collection)
        .order_by(Movie.year.is_(None), Movie.year.asc(), Movie.title.asc(), Movie.id.asc())
        .limit(limit)
        .all()
    )

    lineup = [
        SimilarMovie(
            id=candidate.id,
            title=candidate.title,
            poster_url=candidate.poster_url,
            year=candidate.year,
            flic_score=None,
            poster_theme=select_poster_theme(_extract_genre_labels(candidate)),
            genres=_extract_genre_labels(candidate),
            imdb_rating=candidate.imdb_rating,
            rt_score=candidate.rt_score,
        )
        for candidate in candidates
    ]
    return (collection if lineup else None), lineup


def _merge_similar(
    primary: List[SimilarMovie], fallback: List[SimilarMovie], limit: int = 12
) -> List[SimilarMovie]:
    if len(primary) >= limit:
        return primary[:limit]

    seen = {item.id for item in primary if item.id is not None}
    merged = list(primary)
    for item in fallback:
        if item.id in seen:
            continue
        seen.add(item.id)
        merged.append(item)
        if len(merged) >= limit:
            break

    return merged


def get_movie_detail(
    db: Session, movie_id: int, *, include_provider_similar: bool = False
) -> Optional[MovieDetail]:
    movie = _fetch_movie(db, movie_id)
    if movie is None:
        return None

    try:
        roles = _build_roles(movie)
    except (LookupError, ValueError, StatementError) as exc:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to normalize roles for movie_id=%s: %s", movie_id, exc)
        roles = []
    top_billed: List[TopBilledEntry] = []
    for role in roles:
        role_type = (role.role_type or "").upper()
        if "ACTOR" not in role_type:
            continue
        top_billed.append(
            TopBilledEntry(
                name=role.person.name,
                character=role.character_name,
                imdb_id=role.person.imdb_id,
                person_id=role.person.id,
            )
        )
        if len(top_billed) == 3:
            break
    where_to_watch = split_providers(movie.where_to_watch)

    def _extract_tokens(value: object | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            for key in ("iso_639_1", "iso_3166_1", "english_name", "name"):
                token = value.get(key)
                if token:
                    return [str(token)]
            return [str(value)]
        if isinstance(value, (list, tuple, set)):
            tokens: list[str] = []
            for item in value:
                tokens.extend(_extract_tokens(item))
            return tokens
        return [str(value)]

    def _normalize_tokens(value: object | None) -> str:
        tokens = [token.strip() for token in _extract_tokens(value) if token]
        return "; ".join(token for token in tokens if token)

    def _coerce_text_or_list(value: object | None) -> Optional[str | list[str]]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item is not None]
        if isinstance(value, dict):
            keys = [str(key) for key in value.keys() if key is not None]
            return "; ".join(keys)
        return str(value)

    languages_normalized = normalize_languages(_normalize_tokens(movie.languages))
    countries_normalized = normalize_countries(_normalize_tokens(movie.countries))
    languages_iso = languages_normalized.iso
    countries_iso = countries_normalized.iso
    languages_display = (
        languages_display_from_iso(languages_iso) if languages_iso else languages_normalized.display
    )
    countries_display = (
        countries_display_from_iso(countries_iso) if countries_iso else countries_normalized.display
    )

    collection_lineup_label, collection_lineup = _get_collection_lineup(db, movie)
    similar = _get_tmdb_similar(db, movie) if include_provider_similar else []
    if len(similar) < 12:
        similar_candidates = _get_similarity_candidates(db, movie)
        local_similar = _score_similar(movie, similar_candidates)
        similar = _merge_similar(similar, local_similar)

    trailer_available = bool(
        movie.trailer_site == "youtube"
        and movie.trailer_key
        and YOUTUBE_KEY_RE.fullmatch(movie.trailer_key)
    )

    detail = MovieDetail(
        id=movie.id,
        vault_id=movie.vault_id,
        title=movie.title,
        year=movie.year,
        runtime=movie.runtime,
        plot=movie.plot,
        genres=split_and_normalize([genre.name for genre in movie.genres]),
        moods=[mood.name for mood in movie.moods],
        poster_url=movie.poster_url,
        backdrop_url=movie.backdrop_url,
        imdb_id=movie.imdb_id,
        tmdb_id=movie.tmdb_id,
        imdb_rating=movie.imdb_rating,
        imdb_votes=movie.imdb_votes,
        metascore=movie.metascore,
        tomato_meter=movie.tomato_meter,
        tomato_audience=movie.tomato_audience,
        rt_score=movie.rt_score,
        awards=movie.awards,
        certificate=movie.certificate,
        keywords=list(movie.keywords or []),
        where_to_watch=where_to_watch,
        languages=_coerce_text_or_list(movie.languages),
        countries=_coerce_text_or_list(movie.countries),
        languages_iso=languages_iso,
        countries_iso=countries_iso,
        languages_display=languages_display,
        countries_display=countries_display,
        collection=movie.collection,
        last_tmdb_fetch_at=movie.last_tmdb_fetch_at,
        last_omdb_fetch_at=movie.last_omdb_fetch_at,
        tmdb_etag=movie.tmdb_etag,
        tmdb_payload_sha=movie.tmdb_payload_sha,
        omdb_payload_sha=movie.omdb_payload_sha,
        trailer_site=movie.trailer_site,
        trailer_key=movie.trailer_key,
        trailer_name=movie.trailer_name,
        trailer_url=movie.trailer_url,
        trailer_checked_at=movie.trailer_checked_at,
        trailer_available=trailer_available,
        roles=roles,
        collection_lineup_label=collection_lineup_label,
        collection_lineup=collection_lineup,
        similar=similar,
        poster_theme=select_poster_theme([genre.name for genre in movie.genres]),
        flagged=movie.flag is not None,
        flag_reason=movie.flag.reason if movie.flag is not None else None,
        flag_notes=movie.flag.notes if movie.flag is not None else None,
        top_billed=top_billed,
    )
    return detail


def get_review_neighbors(db: Session, movie_id: int) -> Tuple[Optional[int], Optional[int]]:
    previous_id = (
        db.query(Movie.id).filter(Movie.id < movie_id).order_by(Movie.id.desc()).limit(1).scalar()
    )
    next_id = (
        db.query(Movie.id).filter(Movie.id > movie_id).order_by(Movie.id.asc()).limit(1).scalar()
    )
    return previous_id, next_id


def get_first_movie_id(db: Session) -> Optional[int]:
    return db.query(Movie.id).order_by(Movie.id.asc()).limit(1).scalar()
