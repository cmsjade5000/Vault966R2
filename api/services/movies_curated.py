from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Iterable, List, Sequence

import httpx

from sqlalchemy import Integer, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from api.models.movie import Genre, Movie
from api.models.movie_flag import MovieFlag
from api.models.semantic_search import AiCache
from api.config import settings
from api.services.collection_integrity import get_structural_issue_count
from core.genres import split_and_normalize


@dataclass
class CuratedCollection:
    key: str
    title: str
    description: str
    movies: Sequence[Movie]


@dataclass
class CollectionHealth:
    missing_runtime: int
    missing_plot: int
    missing_poster: int
    genre_gaps: List[str]
    flags_open: int
    recommendation: str | None = None
    structural_issues: int = 0
    source_snapshot_at: datetime | None = None
    source_rows: int = 0
    source_conflicts: int = 0
    identity_review_open: int = 0


class RecommendationError(Exception):
    """Raised when generating the collection health recommendation fails."""


class RecommendationProviderUnavailable(RecommendationError):
    """Raised when the recommendation provider is not configured."""


def _run_base_query(db: Session):
    return db.query(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.moods),
    )


def _first_n(query, limit: int) -> List[Movie]:
    return query.limit(limit).all()


def _genre_filter(query, genres: Iterable[str]):
    normalized = split_and_normalize(genres)
    if not normalized:
        return query
    return query.filter(Movie.genres.any(Genre.name.in_(normalized)))


def _cache_key(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _cache_get(db: Session, key: str) -> dict | None:
    record = db.get(AiCache, key)
    if record is None:
        return None
    expires_at = record.expires_at
    if expires_at:
        if expires_at.tzinfo is None or expires_at.tzinfo.utcoffset(expires_at) is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
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


def _recommendation_facts(db: Session) -> list[dict]:
    facts: list[dict] = []
    collections = (
        db.query(Movie.collection, func.count(Movie.id))
        .filter(Movie.collection.isnot(None))
        .filter(Movie.collection != "")
        .group_by(Movie.collection)
        .having(func.count(Movie.id) <= 2)
        .order_by(func.count(Movie.id).asc(), Movie.collection.asc())
        .all()
    )
    for name, count in collections:
        facts.append({"type": "collection_gap", "collection": name, "count": int(count)})

    genre_counts = (
        db.query(Genre.name, func.count(Movie.id))
        .select_from(Movie)
        .join(Movie.genres)
        .group_by(Genre.name)
        .order_by(func.count(Movie.id).asc(), Genre.name.asc())
        .all()
    )
    if genre_counts:
        total = db.query(func.count(Movie.id)).scalar() or 0
        min_count = min(count for _, count in genre_counts)
        threshold = max(2, int(total * 0.05))
        if min_count <= threshold:
            for name, count in genre_counts:
                if count == min_count:
                    facts.append({"type": "genre_gap", "genre": name, "count": int(count)})

    decade = (cast(Movie.year / 10, Integer) * 10).label("decade")
    decade_counts = (
        db.query(decade, func.count(Movie.id))
        .filter(Movie.year.isnot(None))
        .group_by(decade)
        .order_by(func.count(Movie.id).asc(), decade.asc())
        .all()
    )
    if decade_counts:
        min_count = min(count for _, count in decade_counts)
        for decade_value, count in decade_counts:
            if decade_value and count == min_count and count <= 2:
                facts.append(
                    {"type": "decade_gap", "decade": int(decade_value), "count": int(count)}
                )

    return facts


def _sort_fact_key(fact: dict) -> tuple:
    fact_type = fact.get("type", "")
    if fact_type == "collection_gap":
        return (fact_type, str(fact.get("collection", "")).lower())
    if fact_type == "genre_gap":
        return (fact_type, str(fact.get("genre", "")).lower())
    if fact_type == "decade_gap":
        return (fact_type, int(fact.get("decade", 0)))
    return (fact_type, "")


def _next_fact(db: Session, facts: list[dict]) -> dict:
    ordered = sorted(facts, key=_sort_fact_key)
    if len(ordered) == 1:
        return ordered[0]
    cache_key = _cache_key("collection_health_cycle", "v1")
    cached = _cache_get(db, cache_key)
    last_index = 0
    if cached and isinstance(cached.get("index"), int):
        last_index = cached["index"]
    next_index = (last_index + 1) % len(ordered)
    _cache_set(db, cache_key, {"index": next_index}, settings.semantic_cache_ttl_hours)
    return ordered[next_index]


def _fallback_recommendation(fact: dict) -> str:
    fact_type = fact.get("type")
    if fact_type == "collection_gap":
        count = fact.get("count", 0)
        name = fact.get("collection", "that collection")
        title = "title" if count == 1 else "titles"
        return f"You only have {count} {title} from the {name} collection—worth rounding out."
    if fact_type == "genre_gap":
        count = fact.get("count", 0)
        genre = fact.get("genre", "this genre")
        title = "pick" if count == 1 else "picks"
        return f"Only {count} {genre} {title} so far—consider adding a couple more."
    if fact_type == "decade_gap":
        count = fact.get("count", 0)
        decade = fact.get("decade", "that decade")
        title = "movie" if count == 1 else "movies"
        return f"You’ve got just {count} {title} from the {decade}s—easy spot to expand."
    return "Scan the library for gaps in series, genres, or decades to keep it balanced."


def _fetch_recommendation_text(fact: dict, *, client: httpx.Client | None = None) -> str:
    api_key = settings.llm_api_key
    if not api_key:
        raise RecommendationProviderUnavailable("LLM_API_KEY is not configured")

    base_url = settings.llm_base_url.rstrip("/")
    model = settings.llm_model

    system = (
        "Write a single, friendly sentence recommending a gap to fill in a movie library. "
        "Use only the provided fact. Do not invent titles or facts. "
        "Keep it under 110 characters. Vary phrasing; avoid starting with the same words."
    )
    user = f"Fact: {json.dumps(fact, ensure_ascii=True, sort_keys=True)}"

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.4,
        "max_tokens": 40,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    created_client = client is None
    if client is None:
        client = httpx.Client(timeout=12.0)
    try:
        response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RecommendationError("LLM response missing choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RecommendationError("LLM response missing content")
        return content.strip()
    except httpx.HTTPError as exc:
        raise RecommendationError(f"LLM request failed: {exc}") from exc
    finally:
        if created_client:
            client.close()


def get_collection_recommendation(
    db: Session, *, force: bool = False, allow_provider: bool = True
) -> str | None:
    facts = _recommendation_facts(db)
    if not facts:
        return None
    fact = _next_fact(db, facts) if force else sorted(facts, key=_sort_fact_key)[0]
    fallback = _fallback_recommendation(fact)
    cache_key = _cache_key("collection_health", json.dumps(fact, sort_keys=True))
    cached_text = None
    if not force:
        cached = _cache_get(db, cache_key)
        if cached and isinstance(cached.get("text"), str):
            return cached["text"]
    else:
        cached = _cache_get(db, cache_key)
        if cached and isinstance(cached.get("text"), str):
            cached_text = cached["text"]
    if not allow_provider:
        return fallback
    try:
        text = _fetch_recommendation_text(fact)
    except RecommendationProviderUnavailable:
        return fallback
    except RecommendationError:
        return fallback
    if cached_text and text == cached_text and len(facts) > 1:
        for alt in facts:
            if alt == fact:
                continue
            alt_fallback = _fallback_recommendation(alt)
            alt_key = _cache_key("collection_health", json.dumps(alt, sort_keys=True))
            try:
                alt_text = _fetch_recommendation_text(alt)
            except (RecommendationProviderUnavailable, RecommendationError):
                alt_text = alt_fallback
            _cache_set(
                db,
                alt_key,
                {"text": alt_text},
                settings.semantic_cache_ttl_hours,
            )
            return alt_text
    _cache_set(
        db,
        cache_key,
        {"text": text},
        settings.semantic_cache_ttl_hours,
    )
    return text


def get_curated_collections(
    db: Session, *, items_per_collection: int = 8
) -> List[CuratedCollection]:
    collections: List[CuratedCollection] = []

    quick_hits = _first_n(
        _run_base_query(db)
        .filter(Movie.runtime.isnot(None))
        .filter(Movie.runtime <= 95)
        .order_by(Movie.runtime.asc(), Movie.year.desc()),
        items_per_collection,
    )
    if quick_hits:
        collections.append(
            CuratedCollection(
                key="quick_hits",
                title="Quick Hits",
                description="Crowd-pleasers under 95 minutes when you just want a vibe.",
                movies=quick_hits,
            )
        )

    epic_nights = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.runtime.isnot(None))
            .filter(Movie.runtime >= 140)
            .order_by(Movie.year.desc(), Movie.runtime.desc()),
            ["Adventure", "Epic", "Science Fiction", "Drama"],
        ),
        items_per_collection,
    )
    if epic_nights:
        collections.append(
            CuratedCollection(
                key="epic_night",
                title="Epic Night In",
                description="Big-screen energy—long runtimes, huge stakes, killer scores.",
                movies=epic_nights,
            )
        )

    comfort_nineties = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.year >= 1990)
            .filter(Movie.year <= 1999)
            .order_by(Movie.year.asc(), Movie.title.asc()),
            ["Comedy", "Romance"],
        ),
        items_per_collection,
    )
    if comfort_nineties:
        collections.append(
            CuratedCollection(
                key="comfort_90s",
                title="Comfort 90s",
                description="Feel-good rewatches from the VHS shelf—comfort food for the brain.",
                movies=comfort_nineties,
            )
        )

    documentary_focus = _first_n(
        _genre_filter(
            _run_base_query(db).order_by(Movie.year.desc(), Movie.title.asc()),
            ["Documentary"],
        ),
        items_per_collection,
    )
    if documentary_focus:
        collections.append(
            CuratedCollection(
                key="docs",
                title="Documentary Deep Dive",
                description="Real stories, reflective tones, and the truth-is-stranger moments.",
                movies=documentary_focus,
            )
        )

    high_energy = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.runtime.isnot(None))
            .filter(Movie.runtime <= 120)
            .order_by(Movie.year.desc()),
            ["Action", "Thriller"],
        ),
        items_per_collection,
    )
    if high_energy:
        collections.append(
            CuratedCollection(
                key="high_energy",
                title="High Energy",
                description="Adrenaline-forward picks with tight runtimes and bold moves.",
                movies=high_energy,
            )
        )

    return collections


def get_collection_health(db: Session) -> CollectionHealth:
    base_query = db.query(Movie)

    missing_runtime = base_query.filter(Movie.runtime.is_(None)).count()
    missing_plot = base_query.filter(or_(Movie.plot.is_(None), Movie.plot == "")).count()
    missing_poster = base_query.filter(
        or_(Movie.poster_url.is_(None), Movie.poster_url == "")
    ).count()
    flags_open = db.query(func.count()).select_from(MovieFlag).scalar() or 0

    genre_counts = func.count(Movie.id)
    top_genres = (
        db.query(Genre.name, genre_counts)
        .select_from(Movie)
        .join(Movie.genres)
        .group_by(Genre.name)
        .order_by(genre_counts.desc())
        .limit(5)
        .all()
    )

    genre_gaps: List[str] = []
    if top_genres:
        seen = {name.lower() for name, _ in top_genres}
        aspirational = ["Animation", "Mystery", "Noir", "Western", "Family"]
        genre_gaps = [label for label in aspirational if label.lower() not in seen][:3]

    recommendation = get_collection_recommendation(db, allow_provider=False)
    from api.services.movie_review import get_review_queue
    from api.services.source_sync import (
        get_source_review_queue,
        latest_active_snapshot,
        snapshot_summary,
    )

    latest_snapshot = latest_active_snapshot(db)
    source_summary = snapshot_summary(db, latest_snapshot)
    source_review = get_source_review_queue(db, snapshot=latest_snapshot)
    legacy_review, _ = get_review_queue(db)
    structural_issues = get_structural_issue_count(db)

    return CollectionHealth(
        missing_runtime=missing_runtime,
        missing_plot=missing_plot,
        missing_poster=missing_poster,
        genre_gaps=genre_gaps,
        flags_open=flags_open,
        recommendation=recommendation,
        structural_issues=structural_issues,
        source_snapshot_at=latest_snapshot.confirmed_at if latest_snapshot else None,
        source_rows=source_summary["rows"],
        source_conflicts=source_summary["conflicts"],
        identity_review_open=len(source_review) + len(legacy_review),
    )


__all__ = [
    "CollectionHealth",
    "CuratedCollection",
    "get_curated_collections",
    "get_collection_health",
    "get_collection_recommendation",
]
