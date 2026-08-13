from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Tuple

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.movie import Movie
from api.models.semantic_search import AiCache, MovieDocument
from api.utils.provider_errors import format_provider_error
from core.movie_filters import MovieFilterParams

DOC_VERSION = 1
EMBEDDING_TIMEOUT = 20.0
EMBEDDING_MAX_RETRIES = 3
EMBEDDING_MAX_TEXT = 2000
LOG = logging.getLogger(__name__)


class SemanticSearchUnavailable(Exception):
    """Raised when semantic search cannot run."""


class SemanticSearchError(Exception):
    """Raised when semantic search fails unexpectedly."""


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


@dataclass(frozen=True)
class SemanticIntent:
    params: MovieFilterParams
    boost_genres: tuple[str, ...] = ()
    boost_moods: tuple[str, ...] = ()
    boost_year_range: tuple[int, int] | None = None


def _extract_decade(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b(19|20)\d0s\b", text)
    if match:
        decade = int(match.group(0)[:4])
        return decade, decade + 9
    short = re.search(r"\b(\d{2})s\b", text)
    if not short:
        return None
    decade_suffix = int(short.group(1))
    if decade_suffix in {80, 90}:
        decade = 1900 + decade_suffix
    elif decade_suffix in {0, 10, 20, 30}:
        decade = 2000 + decade_suffix
    else:
        return None
    return decade, decade + 9


def _extract_runtime_bounds(text: str) -> tuple[int | None, int | None]:
    under = re.search(r"\bunder\s+(\d{2,3})\b", text)
    over = re.search(r"\bover\s+(\d{2,3})\b", text)
    if under:
        return None, int(under.group(1))
    if over:
        return int(over.group(1)), None
    if re.search(r"\b(short|quick|snappy)\b", text):
        return None, 100
    if re.search(r"\b(long|epic|lengthy)\b", text):
        return 140, None
    return None, None


def parse_semantic_intent(query: str, params: MovieFilterParams) -> SemanticIntent:
    text = _normalize_query(query).lower()
    boost_genres: set[str] = set()
    boost_moods: set[str] = set()

    genre_phrases = {
        "science fiction": "Science Fiction",
        "sci-fi": "Science Fiction",
        "scifi": "Science Fiction",
        "romcom": "Romance",
        "rom-com": "Romance",
    }
    genre_tokens = {
        "horror": "Horror",
        "thriller": "Thriller",
        "romance": "Romance",
        "comedy": "Comedy",
        "drama": "Drama",
        "action": "Action",
        "adventure": "Adventure",
        "fantasy": "Fantasy",
        "crime": "Crime",
        "mystery": "Mystery",
        "family": "Family",
        "documentary": "Documentary",
        "animation": "Animation",
        "animated": "Animation",
    }
    mood_phrases = {
        "slow burn": "Thoughtful",
        "slow-burn": "Thoughtful",
        "feel good": "Light",
        "feel-good": "Light",
        "mind bending": "Mind-bending",
        "mind-bending": "Mind-bending",
    }
    mood_tokens = {
        "bleak": "Bleak",
        "comfort": "Cozy",
        "cozy": "Cozy",
        "funny": "Funny",
        "gritty": "Gritty",
        "intense": "Intense",
        "light": "Light",
        "moody": "Atmospheric",
        "atmospheric": "Atmospheric",
        "romantic": "Romantic",
        "scary": "Scary",
        "thoughtful": "Thoughtful",
        "reflective": "Thoughtful",
        "fast": "High-energy",
        "fast-paced": "High-energy",
        "high-octane": "High-energy",
        "epic": "Epic",
    }

    for phrase, genre in genre_phrases.items():
        if phrase in text:
            boost_genres.add(genre)
    tokens = set(re.findall(r"[a-z0-9-]+", text))
    for token, genre in genre_tokens.items():
        if token in tokens:
            boost_genres.add(genre)
    for phrase, mood in mood_phrases.items():
        if phrase in text:
            boost_moods.add(mood)
    for token, mood in mood_tokens.items():
        if token in tokens:
            boost_moods.add(mood)

    updated_params = params
    decade = _extract_decade(text)
    boost_year_range = None
    if decade and updated_params.year_min is None and updated_params.year_max is None:
        updated_params = replace(updated_params, year_min=decade[0], year_max=decade[1])
        boost_year_range = decade

    runtime_min, runtime_max = _extract_runtime_bounds(text)
    if runtime_min is not None and updated_params.runtime_min is None:
        updated_params = replace(updated_params, runtime_min=runtime_min)
    if runtime_max is not None and updated_params.runtime_max is None:
        updated_params = replace(updated_params, runtime_max=runtime_max)

    return SemanticIntent(
        params=updated_params,
        boost_genres=tuple(sorted(boost_genres)),
        boost_moods=tuple(sorted(boost_moods)),
        boost_year_range=boost_year_range,
    )


def semantic_query_forces_animation(query: str) -> bool:
    tokens = set(_normalize_query(query).lower().split())
    return bool({"animated", "animation"} & tokens)


def apply_semantic_query_overrides(query: str, params: MovieFilterParams) -> MovieFilterParams:
    if semantic_query_forces_animation(query):
        if "Animation" not in params.genres:
            return replace(params, genres=params.genres + ("Animation",))
    return params


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _embedding_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _pgvector_available(db: Session) -> bool:
    try:
        row = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
        return row is not None
    except Exception:
        return False


def semantic_search_enabled(db: Session) -> bool:
    return (
        settings.semantic_search_enabled
        and settings.llm_api_key is not None
        and _is_postgres(db)
        and _pgvector_available(db)
    )


def build_movie_document(movie: Movie) -> str:
    genres = ", ".join(sorted({g.name for g in movie.genres if g.name}))
    moods = ", ".join(sorted({m.name for m in movie.moods if m.name}))
    parts: list[str] = []
    if movie.title:
        parts.append(movie.title)
    if movie.year:
        parts.append(str(movie.year))
    if movie.collection:
        parts.append(f"Collection: {movie.collection}")
    if movie.plot:
        parts.append(movie.plot)
    if genres:
        parts.append(f"Genres: {genres}")
    if moods:
        parts.append(f"Moods: {moods}")
    text_value = "\n".join(parts).strip()
    if len(text_value) > EMBEDDING_MAX_TEXT:
        text_value = text_value[:EMBEDDING_MAX_TEXT].rstrip()
    return text_value


def _fetch_embeddings(texts: List[str]) -> List[List[float]]:
    if not settings.llm_api_key:
        raise SemanticSearchUnavailable("Embeddings provider not configured")

    url = f"{settings.llm_base_url.rstrip('/')}/embeddings"
    payload = {"model": settings.llm_embedding_model, "input": texts}
    last_error: Exception | None = None
    for attempt in range(EMBEDDING_MAX_RETRIES):
        try:
            response = httpx.post(
                url,
                headers=_embedding_headers(),
                json=payload,
                timeout=EMBEDDING_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            last_error = SemanticSearchError(
                format_provider_error("Embeddings request failed", exc)
            )
        else:
            if response.status_code == 200:
                try:
                    data = response.json()
                except (TypeError, ValueError):
                    malformed_response = True
                else:
                    malformed_response = False
                if malformed_response:
                    raise SemanticSearchError("Embeddings response was malformed")
                return _validate_embeddings_response(data, expected_count=len(texts))

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = SemanticSearchError(
                    f"Embeddings provider returned {response.status_code}"
                )
            else:
                raise SemanticSearchError(f"Embeddings provider returned {response.status_code}")

        sleep_for = min(2.0**attempt, 6.0)
        time.sleep(sleep_for)

    LOG.warning(
        "Embeddings request failed after retries",
        extra={"status": "failed", "attempts": EMBEDDING_MAX_RETRIES},
    )
    raise SemanticSearchError("Embeddings request failed") from last_error


def _validate_embedding_vector(value: object) -> List[float]:
    if not isinstance(value, list) or len(value) != settings.llm_embedding_dim:
        raise SemanticSearchError("Embeddings response contained an invalid vector dimension")

    vector: List[float] = []
    for element in value:
        if isinstance(element, bool) or not isinstance(element, (int, float)):
            raise SemanticSearchError("Embeddings response contained a non-numeric vector value")
        try:
            normalized = float(element)
        except (OverflowError, TypeError, ValueError) as exc:
            raise SemanticSearchError(
                "Embeddings response contained a non-numeric vector value"
            ) from exc
        if not math.isfinite(normalized):
            raise SemanticSearchError("Embeddings response contained a non-finite vector value")
        vector.append(normalized)
    return vector


def _validate_embeddings_response(value: object, *, expected_count: int) -> List[List[float]]:
    if not isinstance(value, dict):
        raise SemanticSearchError("Embeddings response was malformed")

    items = value.get("data")
    if not isinstance(items, list) or len(items) != expected_count:
        raise SemanticSearchError("Embeddings response contained an invalid vector count")

    ordered: List[List[float] | None] = [None] * expected_count
    for entry in items:
        if not isinstance(entry, dict):
            raise SemanticSearchError("Embeddings response contained an invalid item")
        index = entry.get("index")
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= expected_count
            or ordered[index] is not None
        ):
            raise SemanticSearchError("Embeddings response contained invalid indices")
        ordered[index] = _validate_embedding_vector(entry.get("embedding"))

    if any(vector is None for vector in ordered):
        raise SemanticSearchError("Embeddings response contained invalid indices")
    return [vector for vector in ordered if vector is not None]


def _cache_key(prefix: str, value: str) -> str:
    return f"{prefix}:{_hash_text(value)}"


def _cache_get(db: Session, key: str) -> dict | None:
    record = db.get(AiCache, key)
    if record is None:
        return None
    if record.expires_at and record.expires_at <= datetime.now(timezone.utc):
        db.delete(record)
        db.commit()
        return None
    if isinstance(record.value, dict):
        return record.value
    try:
        return json.loads(record.value)
    except Exception:
        return None


def _cache_set(db: Session, key: str, value: dict, ttl_hours: int) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    record = AiCache(
        cache_key=key,
        value=value,
        expires_at=expires_at,
        created_at=datetime.now(timezone.utc),
    )
    db.merge(record)
    db.commit()


def get_query_embedding(db: Session, query: str) -> List[float]:
    normalized = _normalize_query(query)
    cache_key = _cache_key("embedding", f"{settings.llm_embedding_model}:{normalized}")
    cached = _cache_get(db, cache_key)
    if cached and isinstance(cached.get("embedding"), list):
        try:
            return _validate_embedding_vector(cached["embedding"])
        except SemanticSearchError:
            pass

    embedding = _fetch_embeddings([normalized])[0]
    _cache_set(
        db,
        cache_key,
        {"embedding": embedding, "model": settings.llm_embedding_model},
        settings.semantic_cache_ttl_hours,
    )
    return embedding


def _chunked(values: Iterable[Tuple[Movie, str]], size: int) -> Iterable[List]:
    batch: List = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def backfill_movie_documents(
    db: Session,
    *,
    limit: int | None = None,
    after_id: int | None = None,
) -> Tuple[int, int]:
    if not semantic_search_enabled(db):
        raise SemanticSearchUnavailable("Semantic search is not enabled")

    query = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .order_by(Movie.id.asc())
    )
    if after_id is not None:
        query = query.filter(Movie.id > after_id)
    if limit:
        query = query.limit(limit)
    movies = query.all()

    existing = {doc.movie_id: doc for doc in db.query(MovieDocument).all()}

    to_embed: List[Tuple[Movie, str]] = []
    for movie in movies:
        content = build_movie_document(movie)
        current = existing.get(movie.id)
        if current and current.doc_version == DOC_VERSION and current.content == content:
            continue
        to_embed.append((movie, content))

    created = 0
    updated = 0
    for batch in _chunked(to_embed, settings.semantic_backfill_batch):
        embeddings = _fetch_embeddings([entry[1] for entry in batch])
        now = datetime.now(timezone.utc)
        for (movie, content), vector in zip(batch, embeddings, strict=True):
            current = existing.get(movie.id)
            if current:
                current.doc_version = DOC_VERSION
                current.content = content
                current.embedding = vector
                current.updated_at = now
                updated += 1
            else:
                db.add(
                    MovieDocument(
                        movie_id=movie.id,
                        doc_version=DOC_VERSION,
                        content=content,
                        embedding=vector,
                        updated_at=now,
                    )
                )
                created += 1
        db.commit()
        time.sleep(settings.semantic_backfill_sleep)

    return created, updated


def _build_semantic_candidate_query(
    db: Session,
    *,
    embedding: List[float],
    filtered_query,
    limit: int,
):
    distance = MovieDocument.embedding.l2_distance(embedding)
    candidate_query = db.query(Movie, distance.label("distance")).join(
        MovieDocument, MovieDocument.movie_id == Movie.id
    )
    candidate_query = filtered_query(candidate_query)
    return candidate_query.order_by(distance.asc(), Movie.id.asc()).limit(limit)


def semantic_search_movies(
    db: Session,
    *,
    query: str,
    filtered_query,
    limit: int,
    page: int,
    page_size: int,
    intent: SemanticIntent | None = None,
) -> Tuple[List[Tuple[Movie, float]], int]:
    if not semantic_search_enabled(db):
        raise SemanticSearchUnavailable("Semantic search is not enabled")

    embedding = get_query_embedding(db, query)

    candidate_query = _build_semantic_candidate_query(
        db,
        embedding=embedding,
        filtered_query=filtered_query,
        limit=limit,
    )
    rows = candidate_query.options(selectinload(Movie.genres), selectinload(Movie.moods)).all()
    if not rows:
        return [], 0

    total = len(rows)
    boost_genres = set(intent.boost_genres) if intent else set()
    boost_moods = set(intent.boost_moods) if intent else set()
    boost_year_range = intent.boost_year_range if intent else None

    scored_rows = []
    for movie, distance in rows:
        score = 1.0 / (1.0 + float(distance))
        if boost_genres and getattr(movie, "genres", None):
            genre_names = {getattr(genre, "name", None) for genre in movie.genres} - {None}
            if genre_names:
                matches = len(genre_names & boost_genres)
                score += min(matches * 0.08, 0.24)
        if boost_moods and getattr(movie, "moods", None):
            mood_names = {getattr(mood, "name", None) for mood in movie.moods} - {None}
            if mood_names:
                matches = len(mood_names & boost_moods)
                score += min(matches * 0.05, 0.15)
        if boost_year_range and movie.year:
            if boost_year_range[0] <= movie.year <= boost_year_range[1]:
                score += 0.03
        scored_rows.append((movie, distance, score))

    scored_rows.sort(key=lambda row: (-row[2], float(row[1]), row[0].id))
    page_offset = (page - 1) * page_size
    paged = scored_rows[page_offset : page_offset + page_size]
    return [(row[0], row[1]) for row in paged], total
