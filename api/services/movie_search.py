from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Query, Session, selectinload

from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from api.models.movie_flag import MovieFlag
from api.services.movie_filters import MovieFilterParams, apply_filters, ordering_clause
from api.utils.pagination import paginate
from core.genres import split_and_normalize
from core.picker import calculate_flic_score


@dataclass
class MovieSearchResult:
    items: List[Movie]
    total: int
    facets: Dict[str, Dict[str, int]]
    page: int


def _score_movies_for_flic(movies: Sequence[Movie], params: MovieFilterParams) -> List[Tuple[float, Movie]]:
    filters = {
        "genres": split_and_normalize(params.genres),
        "moods": list(params.moods),
        "runtime_min": params.runtime_min,
        "runtime_max": params.runtime_max,
        "year_min": params.year_min,
        "year_max": params.year_max,
    }
    scored: List[Tuple[float, Movie]] = []
    for movie in movies:
        candidate = {
            "genres": split_and_normalize([genre.name for genre in movie.genres]),
            "moods": [mood.name for mood in movie.moods],
            "runtime": movie.runtime,
            "year": movie.year,
        }
        score, _ = calculate_flic_score(candidate, filters)
        scored.append((score, movie))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _build_facets(db: Session, filtered_query: Query) -> Dict[str, Dict[str, int]]:
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

    return {
        "genres": genre_counts,
        "moods": mood_counts,
    }


def search_movies(
    db: Session,
    params: MovieFilterParams,
    *,
    page: int,
    page_size: int,
    clamp_page: bool = False,
) -> MovieSearchResult:
    base_query = db.query(Movie)
    filtered_query = apply_filters(base_query, params)

    effective_page = max(page, 1)

    if params.order_by == "flic":
        movies = (
            filtered_query.options(selectinload(Movie.genres), selectinload(Movie.moods)).all()
        )
        scored = _score_movies_for_flic(movies, params)
        total = len(scored)
        if clamp_page:
            if total == 0:
                effective_page = 1
            else:
                max_page = (total + page_size - 1) // page_size
                effective_page = min(effective_page, max_page)
        start = (effective_page - 1) * page_size
        end = start + page_size
        items = [movie for _, movie in scored[start:end]]
    else:
        clause = ordering_clause(params.order_by)
        ordered_query = filtered_query.options(
            selectinload(Movie.genres), selectinload(Movie.moods)
        ).order_by(clause)
        items, total = paginate(ordered_query, page=effective_page, page_size=page_size)
        if clamp_page and total > 0:
            max_page = (total + page_size - 1) // page_size
            if effective_page > max_page:
                effective_page = max_page
                items, total = paginate(ordered_query, page=effective_page, page_size=page_size)
        elif clamp_page and total == 0:
            effective_page = 1

    facets = _build_facets(db, filtered_query)
    return MovieSearchResult(items=items, total=total, facets=facets, page=effective_page)


def attach_flag_status(db: Session, movies: Sequence[Movie]) -> None:
    if not movies:
        return
    ids = [movie.id for movie in movies if movie.id is not None]
    if not ids:
        return
    flagged_ids = {
        row[0]
        for row in db.query(MovieFlag.movie_id).filter(MovieFlag.movie_id.in_(ids)).all()
    }
    for movie in movies:
        setattr(movie, "flagged", movie.id in flagged_ids)


__all__ = ["MovieSearchResult", "search_movies", "attach_flag_status"]
