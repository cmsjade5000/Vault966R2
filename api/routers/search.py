from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.deps.auth import require_same_origin_provider_work
from api.models.movie import Movie
from api.schemas.movie import MovieFacets
from api.schemas.semantic_search import (
    SemanticSearchItem,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from api.services.semantic_search import (
    SemanticSearchError,
    SemanticSearchUnavailable,
    apply_semantic_query_overrides,
    parse_semantic_intent,
    semantic_query_forces_animation,
    semantic_search_enabled,
    semantic_search_movies,
)
from core.movie_filters import MovieFilterParams, apply_filters, parse_movie_filters
from api.routers.movies import _attach_flag_status, _build_facets

router = APIRouter(prefix="/api/search", tags=["search"])
LOG = logging.getLogger(__name__)


def _query_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _keyword_fallback(
    db: Session,
    *,
    query: str,
    params: MovieFilterParams,
    page: int,
    page_size: int,
    notice: str,
) -> SemanticSearchResponse:
    base_query = db.query(Movie)
    params_with_query = MovieFilterParams(
        q=query,
        year_min=params.year_min,
        year_max=params.year_max,
        runtime_min=params.runtime_min,
        runtime_max=params.runtime_max,
        genres=params.genres,
        moods=params.moods,
        order_by="title_asc",
    )
    filtered_query = apply_filters(base_query, params_with_query)
    total = filtered_query.count()
    items = (
        filtered_query.order_by(Movie.title.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    _attach_flag_status(db, items)
    facets = MovieFacets(**_build_facets(db, filtered_query))
    response_items = [
        SemanticSearchItem.model_validate(
            {**item.__dict__, "similarity_score": 0.0},
        )
        for item in items
    ]
    return SemanticSearchResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        facets=facets,
        mode="keyword",
        notice=notice,
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    payload: SemanticSearchRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin_provider_work("semantic_search")),
):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    params: MovieFilterParams = parse_movie_filters(
        q=None,
        year_min=payload.year_min,
        year_max=payload.year_max,
        runtime_min=payload.runtime_min,
        runtime_max=payload.runtime_max,
        genres=payload.genres,
        moods=payload.moods,
        order_by="title_asc",
    )
    params = apply_semantic_query_overrides(query, params)
    intent = parse_semantic_intent(query, params)
    params = intent.params
    LOG.info(
        "semantic_search_intent",
        extra={
            "query_hash": _query_hash(query),
            "boost_genres": list(intent.boost_genres),
            "boost_moods": list(intent.boost_moods),
            "boost_year_range": intent.boost_year_range,
            "runtime_min": params.runtime_min,
            "runtime_max": params.runtime_max,
            "year_min": params.year_min,
            "year_max": params.year_max,
        },
    )

    if not semantic_search_enabled(db):
        LOG.info(
            "Semantic search disabled; falling back to keyword search",
            extra={"query_hash": _query_hash(query), "fallback_reason": "disabled"},
        )
        return _keyword_fallback(
            db,
            query=query,
            params=params,
            page=payload.page,
            page_size=payload.page_size,
            notice="Semantic search unavailable; showing title matches instead.",
        )

    def apply_filtering(queryset):
        return apply_filters(queryset, params)

    limit = settings.semantic_search_top_k
    if semantic_query_forces_animation(query):
        limit = min(max(limit * 5, 500), 2000)

    try:
        rows, total = semantic_search_movies(
            db,
            query=query,
            filtered_query=apply_filtering,
            limit=limit,
            page=payload.page,
            page_size=payload.page_size,
            intent=intent,
        )
    except SemanticSearchUnavailable:
        LOG.info(
            "Semantic search unavailable; falling back to keyword search",
            extra={"query_hash": _query_hash(query), "fallback_reason": "unavailable"},
        )
        return _keyword_fallback(
            db,
            query=query,
            params=params,
            page=payload.page,
            page_size=payload.page_size,
            notice="Semantic search unavailable; showing title matches instead.",
        )
    except SemanticSearchError:
        LOG.warning(
            "Semantic search failed; falling back to keyword search",
            extra={"query_hash": _query_hash(query), "fallback_reason": "error"},
        )
        return _keyword_fallback(
            db,
            query=query,
            params=params,
            page=payload.page,
            page_size=payload.page_size,
            notice="Semantic search failed; showing title matches instead.",
        )

    if not rows:
        LOG.info(
            "Semantic search empty; falling back to keyword search",
            extra={"query_hash": _query_hash(query), "fallback_reason": "empty"},
        )
        return _keyword_fallback(
            db,
            query=query,
            params=params,
            page=payload.page,
            page_size=payload.page_size,
            notice="No semantic matches yet; showing title matches instead.",
        )

    movies = [row[0] for row in rows]
    _attach_flag_status(db, movies)
    base_query = db.query(Movie)
    filtered_query = apply_filters(base_query, params)
    facets = MovieFacets(**_build_facets(db, filtered_query))

    items = []
    for movie, distance in rows:
        score = 1.0 / (1.0 + float(distance))
        items.append(
            SemanticSearchItem.model_validate({**movie.__dict__, "similarity_score": score})
        )
    LOG.info(
        "semantic_search_success",
        extra={
            "query_hash": _query_hash(query),
            "total": total,
            "returned": len(items),
        },
    )

    return SemanticSearchResponse(
        items=items,
        total=total,
        page=payload.page,
        page_size=payload.page_size,
        facets=facets,
        mode="semantic",
    )
