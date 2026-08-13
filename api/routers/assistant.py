from __future__ import annotations

import hashlib
import logging
import re
from typing import Iterable, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.db import get_db
from api.deps.auth import require_provider_work_budget, require_same_origin
from api.models.movie import Movie
from api.schemas.assistant import AssistantMovie, AssistantRequest, AssistantResponse
from api.services.assistant import (
    AssistantError,
    AssistantProviderUnavailable,
    generate_assistant_template,
)
from api.services.semantic_search import (
    SemanticSearchError,
    SemanticSearchUnavailable,
    semantic_search_enabled,
    semantic_search_movies,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
LOG = logging.getLogger(__name__)


def _query_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _rating_score(movie: Movie) -> float:
    imdb = float(movie.imdb_rating or 0.0)
    rt = float(movie.rt_score or 0.0) / 10.0
    return imdb * 1.2 + rt * 0.8


def _movie_payload(movie: Movie) -> AssistantMovie:
    genres = [genre.name for genre in movie.genres if getattr(genre, "name", None)]
    moods = [mood.name for mood in movie.moods if getattr(mood, "name", None)]
    return AssistantMovie(
        id=movie.id,
        title=movie.title,
        year=movie.year,
        runtime=movie.runtime,
        imdb_rating=movie.imdb_rating,
        rt_score=movie.rt_score,
        genres=genres,
        moods=moods,
    )


def _catalog_payload(movie: Movie) -> dict:
    return {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "genres": [genre.name for genre in movie.genres if getattr(genre, "name", None)],
        "moods": [mood.name for mood in movie.moods if getattr(mood, "name", None)],
        "imdb_rating": movie.imdb_rating,
        "rt_score": movie.rt_score,
    }


def _render_template(template: str, movies: Iterable[Movie], followup: str) -> str:
    reply = template
    movie_list = list(movies)
    for idx, movie in enumerate(movie_list, start=1):
        reply = reply.replace(f"{{{{movie_{idx}}}}}", movie.title)
    for idx in range(len(movie_list) + 1, 4):
        reply = reply.replace(f"{{{{movie_{idx}}}}}", "")
    reply = re.sub(r"\s{2,}", " ", reply).strip()
    if followup:
        reply = f"{reply} {followup}".strip()
    return reply


def _fallback_reply(movies: Iterable[Movie]) -> str:
    titles = [movie.title for movie in movies if movie.title]
    if not titles:
        return "Vault picks are ready."
    if len(titles) == 1:
        return f"Vault pick: {titles[0]}."
    if len(titles) == 2:
        return f"Vault picks: {titles[0]} and {titles[1]}."
    return f"Vault picks: {titles[0]}, {titles[1]}, and {titles[2]}."


def _sanitize_reply(reply: str, query: str, picks: Iterable[Movie]) -> str:
    cleaned = reply.strip()
    query_clean = query.strip()
    if not cleaned or not query_clean:
        return cleaned
    pick_titles = {movie.title.lower() for movie in picks if getattr(movie, "title", None)}
    if query_clean.lower() in pick_titles:
        return cleaned
    lowered_query = query_clean.lower()
    if lowered_query in cleaned.lower():
        cleaned = re.sub(re.escape(query_clean), "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _select_diverse_movies(movies: List[Movie], pick_count: int) -> List[Movie]:
    picks: List[Movie] = []
    used_genres: set[str] = set()
    for movie in movies:
        movie_genres = {genre.name for genre in movie.genres if getattr(genre, "name", None)}
        if not picks:
            picks.append(movie)
            used_genres |= movie_genres
        else:
            if not movie_genres or movie_genres.isdisjoint(used_genres):
                picks.append(movie)
                used_genres |= movie_genres
        if len(picks) >= pick_count:
            break

    if len(picks) < pick_count:
        for movie in movies:
            if movie not in picks:
                picks.append(movie)
            if len(picks) >= pick_count:
                break

    return picks


def _semantic_candidates(db: Session, query: str, limit: int) -> List[Movie]:
    if not semantic_search_enabled(db):
        return []

    def _apply_filters(queryset):
        return queryset

    limit = min(settings.semantic_search_top_k, max(limit * 8, 50))

    try:
        rows, _ = semantic_search_movies(
            db,
            query=query,
            filtered_query=_apply_filters,
            limit=limit,
            page=1,
            page_size=limit,
            intent=None,
        )
    except (SemanticSearchUnavailable, SemanticSearchError):
        return []

    return [row[0] for row in rows]


def _keyword_candidates(db: Session, query: str, limit: int) -> List[Movie]:
    like = f"%{query}%"
    base_query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    return (
        base_query.filter(
            or_(
                Movie.title.ilike(like),
                Movie.plot.ilike(like),
                Movie.collection.ilike(like),
            )
        )
        .order_by(Movie.title.asc())
        .limit(max(limit * 8, 30))
        .all()
    )


def _fallback_candidates(db: Session, limit: int) -> List[Movie]:
    base_query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    return (
        base_query.order_by(
            func.coalesce(Movie.imdb_rating, 0).desc(),
            func.coalesce(Movie.rt_score, 0).desc(),
            Movie.title.asc(),
        )
        .limit(max(limit * 8, 30))
        .all()
    )


def _wants_text(request: Request) -> bool:
    if request.query_params.get("format") == "text":
        return True
    accept = request.headers.get("accept", "")
    return "text/plain" in accept.lower()


def _assistant_logic(
    *,
    query: str,
    limit: int,
    request: Request,
    db: Session,
    use_provider: bool = True,
):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    LOG.info("assistant_query", extra={"query_hash": _query_hash(query)})

    candidates = _semantic_candidates(db, query, limit)
    if not candidates:
        candidates = _keyword_candidates(db, query, limit)
    if not candidates:
        candidates = _fallback_candidates(db, limit)
    if not candidates:
        reply = "The vault is empty right now. Add a few movies to get picks."
        if _wants_text(request):
            return PlainTextResponse(reply, media_type="text/plain; charset=utf-8")
        return AssistantResponse(reply=reply, movies=[])

    top_candidates = candidates[: max(limit * 6, 12)]
    top_candidates = sorted(top_candidates, key=_rating_score, reverse=True)

    catalog = [_catalog_payload(movie) for movie in top_candidates[:12]]

    template = None
    if use_provider:
        try:
            template = generate_assistant_template(query, movies=catalog)
        except AssistantProviderUnavailable:
            LOG.info(
                "assistant_llm_unavailable",
                extra={"query_hash": _query_hash(query)},
            )
        except AssistantError:
            LOG.warning(
                "assistant_llm_error",
                extra={"query_hash": _query_hash(query)},
            )

    if template:
        pick_count = min(max(template.pick_count, 1), limit)
        picks = _select_diverse_movies(top_candidates, pick_count)
        reply = _render_template(template.template, picks, template.followup)
        reply = _sanitize_reply(reply, query, picks)
        if not reply:
            reply = _fallback_reply(picks)
    else:
        pick_count = min(3, limit)
        picks = _select_diverse_movies(top_candidates, pick_count)
        reply = _fallback_reply(picks)

    reply = _sanitize_reply(reply, query, picks)

    response = AssistantResponse(
        reply=reply,
        movies=[_movie_payload(movie) for movie in picks],
    )

    if _wants_text(request):
        return PlainTextResponse(response.reply, media_type="text/plain; charset=utf-8")

    return response


def _require_same_origin_for_session(request: Request) -> None:
    token = settings.assistant_access_token
    authorization = request.headers.get("Authorization", "")
    if token and authorization.lower().startswith("bearer "):
        if authorization[7:].strip() == token:
            return
    if token:
        header_token = (
            request.headers.get("X-Vault-Assistant-Token")
            or request.headers.get("X-Assistant-Token")
            or ""
        )
        if header_token == token:
            return
    if getattr(request.state, "session_profile_id", None):
        require_same_origin(request)


def _require_assistant_provider_work(request: Request) -> None:
    _require_same_origin_for_session(request)
    require_provider_work_budget(request, scope="assistant")


@router.post("", response_model=AssistantResponse)
def assistant_reply(
    payload: AssistantRequest,
    request: Request,
    _: None = Depends(_require_assistant_provider_work),
    db: Session = Depends(get_db),
):
    return _assistant_logic(
        query=payload.query,
        limit=payload.limit,
        request=request,
        db=db,
        use_provider=True,
    )


@router.get("", response_model=AssistantResponse)
def assistant_reply_get(
    request: Request,
    q: str = Query(min_length=2, max_length=400),
    limit: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
):
    return _assistant_logic(
        query=q,
        limit=limit,
        request=request,
        db=db,
        use_provider=False,
    )
