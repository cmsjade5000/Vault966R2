from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Tuple

import httpx
from sqlalchemy import func, text
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.movie import Movie
from api.models.semantic_search import AiCache, MovieDocument
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
            last_error = exc
        else:
            if response.status_code == 200:
                data = response.json()
                items = data.get("data")
                if not isinstance(items, list):
                    raise SemanticSearchError("Embeddings response was malformed")
                embeddings: List[List[float]] = []
                for entry in sorted(items, key=lambda item: item.get("index", 0)):
                    embedding = entry.get("embedding")
                    if not isinstance(embedding, list):
                        raise SemanticSearchError("Embeddings response missing vectors")
                    embeddings.append(embedding)
                return embeddings

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
        return cached["embedding"]

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
        for (movie, content), vector in zip(batch, embeddings):
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


def semantic_search_movies(
    db: Session,
    *,
    query: str,
    filtered_query,
    limit: int,
    page: int,
    page_size: int,
) -> Tuple[List[Tuple[Movie, float]], int]:
    if not semantic_search_enabled(db):
        raise SemanticSearchUnavailable("Semantic search is not enabled")

    embedding = get_query_embedding(db, query)

    base_query = (
        db.query(Movie.id, MovieDocument.embedding.l2_distance(embedding).label("distance"))
        .join(MovieDocument, MovieDocument.movie_id == Movie.id)
        .order_by(text("distance asc"))
        .limit(limit)
    )

    top_rows = base_query.all()
    if not top_rows:
        return [], 0

    top_ids = [row[0] for row in top_rows if row[0] is not None]
    if not top_ids:
        return [], 0

    filtered_base = (
        db.query(Movie, MovieDocument.embedding.l2_distance(embedding).label("distance"))
        .join(MovieDocument, MovieDocument.movie_id == Movie.id)
        .filter(Movie.id.in_(top_ids))
    )
    filtered_query = filtered_query(filtered_base)
    filtered_query = filtered_query.order_by(text("distance asc"))

    total = filtered_query.order_by(None).with_entities(func.count(Movie.id)).scalar() or 0
    if total == 0:
        return [], 0

    page_offset = (page - 1) * page_size
    rows = (
        filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods))
        .offset(page_offset)
        .limit(page_size)
        .all()
    )
    return [(row[0], row[1]) for row in rows], total
