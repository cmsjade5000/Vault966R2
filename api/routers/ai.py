from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.schemas.ai_search import AiSearchRequest, AiSearchResponse
from api.services.ai_search import (
    AiSearchError,
    AiSearchProviderUnavailable,
    generate_search_plan,
    summarize_search_plan,
)
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from api.utils.pagination import paginate
from core.movie_filters import (
    MovieFilterParams,
    apply_filters,
    ordering_clause,
    parse_movie_filters,
)
from core.picker import PickerFilters
from api.routers.movies import _attach_flag_status


router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = logging.getLogger("vault966")


@router.post("/search", response_model=AiSearchResponse)
def ai_search(
    payload: AiSearchRequest,
    db: Session = Depends(get_db),
):
    allowed_genres = [
        row[0] for row in db.query(Genre.name).order_by(Genre.name.asc()).all() if row[0]
    ]
    allowed_moods = [
        row[0] for row in db.query(Mood.name).order_by(Mood.name.asc()).all() if row[0]
    ]
    try:
        plan = generate_search_plan(
            payload.query,
            allowed_genres=allowed_genres,
            allowed_moods=allowed_moods,
        )
    except AiSearchProviderUnavailable as exc:
        logger.warning("ai_search_provider_unavailable: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="AI search is temporarily unavailable.",
        ) from exc
    except AiSearchError as exc:
        logger.warning("ai_search_provider_failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="AI search could not be completed. Please try again.",
        ) from exc

    params: MovieFilterParams = parse_movie_filters(
        q=plan.q,
        year_min=plan.year_min,
        year_max=plan.year_max,
        runtime_min=plan.runtime_min,
        runtime_max=plan.runtime_max,
        genres=plan.genres,
        moods=plan.moods,
        order_by=plan.order_by,
    )

    base_query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    filtered_query = apply_filters(base_query, params)

    page = payload.page
    page_size = payload.page_size

    if params.order_by == "flic":
        filters = PickerFilters.from_params(params).to_payload()
        ranked = rank_movie_ids_by_flic(db, base_query=filtered_query, filters=filters)
        total = len(ranked)
        start = (page - 1) * page_size
        end = start + page_size
        page_ids = [movie_id for _, movie_id in ranked[start:end]]
        items = fetch_movies_in_rank_order(
            db,
            ranked_ids=page_ids,
            options=[selectinload(Movie.genres), selectinload(Movie.moods)],
        )
        _attach_flag_status(db, items)
    else:
        clause = ordering_clause(params.order_by)
        ordered_query = filtered_query.order_by(*clause)
        items, total = paginate(ordered_query, page=page, page_size=page_size)
        _attach_flag_status(db, items)

    movie_ids_subquery = filtered_query.with_entities(Movie.id.label("movie_id")).subquery()

    genre_counts = dict(
        db.query(Genre.name, func.count())
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(movie_ids_subquery, movie_ids_subquery.c.movie_id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .all()
    )

    mood_counts = dict(
        db.query(Mood.name, func.count())
        .join(movie_moods, Mood.id == movie_moods.c.mood_id)
        .join(movie_ids_subquery, movie_ids_subquery.c.movie_id == movie_moods.c.movie_id)
        .group_by(Mood.name)
        .all()
    )

    facets = {
        "genres": genre_counts,
        "moods": mood_counts,
    }

    explanation = summarize_search_plan(plan)

    return AiSearchResponse(
        plan=plan,
        explanation=explanation,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        facets=facets,
    )
