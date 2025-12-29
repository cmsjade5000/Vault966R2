from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session, selectinload

from api.models.movie import Genre, Mood, Movie
from api.services.flic_ordering import fetch_movies_in_rank_order, rank_movie_ids_by_flic
from core.picker import PickerCandidate, PickerFilters, calculate_flic_score

DEFAULT_DOUBLE_FEATURE_RUNTIME = 220


@dataclass(frozen=True)
class DoubleFeatureSelection:
    primary: Movie
    secondary: Movie
    runtime_cap: int
    total_runtime: int


def _movie_genres(movie: Movie) -> list[str]:
    return [genre.name for genre in getattr(movie, "genres", []) if genre.name]


def _movie_moods(movie: Movie) -> list[str]:
    return [mood.name for mood in getattr(movie, "moods", []) if mood.name]


def _decade_range(year: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if year is None:
        return None, None
    decade_start = (year // 10) * 10
    return decade_start, decade_start + 9


def _filters_from_movie(movie: Movie) -> dict[str, object]:
    year_min, year_max = _decade_range(movie.year)
    filters = PickerFilters.from_values(
        genres=_movie_genres(movie),
        moods=_movie_moods(movie),
        year_min=year_min,
        year_max=year_max,
    )
    return filters.to_payload()


def _complement_score(candidate: Movie, *, filters: dict[str, object]) -> float:
    payload = PickerCandidate.from_iterables(
        genres=_movie_genres(candidate),
        moods=_movie_moods(candidate),
        runtime=candidate.runtime,
        year=candidate.year,
    ).to_payload()
    score, _ = calculate_flic_score(payload, filters)
    return score


def pick_double_feature(
    db: Session,
    *,
    runtime_cap: int,
    genre: Optional[str] = None,
    mood: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> Optional[DoubleFeatureSelection]:
    base_query = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .filter(Movie.runtime.isnot(None))
        .filter(Movie.runtime <= runtime_cap)
    )

    if genre:
        base_query = base_query.filter(Movie.genres.any(Genre.name == genre))
    if mood:
        base_query = base_query.filter(Movie.moods.any(Mood.name == mood))
    if year_min is not None:
        base_query = base_query.filter(Movie.year >= year_min)
    if year_max is not None:
        base_query = base_query.filter(Movie.year <= year_max)

    filters = PickerFilters.from_values(
        genres=[genre] if genre else (),
        moods=[mood] if mood else (),
        runtime_max=runtime_cap,
        year_min=year_min,
        year_max=year_max,
    ).to_payload()

    ranked = rank_movie_ids_by_flic(db, base_query=base_query, filters=filters)
    if len(ranked) < 2:
        return None

    ranked_ids = [movie_id for _, movie_id in ranked]
    ranked_movies = fetch_movies_in_rank_order(
        db,
        ranked_ids=ranked_ids,
        options=[selectinload(Movie.genres), selectinload(Movie.moods)],
    )

    ranked_by_id = {movie.id: movie for movie in ranked_movies if movie.id is not None}
    ordered_movies = [ranked_by_id[movie_id] for movie_id in ranked_ids if movie_id in ranked_by_id]

    for primary in ordered_movies:
        if primary.runtime is None:
            continue
        remaining = runtime_cap - primary.runtime
        if remaining <= 0:
            continue

        complement_pool = [
            movie
            for movie in ordered_movies
            if movie.id != primary.id
            and movie.runtime is not None
            and movie.runtime <= remaining
        ]
        if not complement_pool:
            continue

        complement_filters = _filters_from_movie(primary)
        secondary = max(
            complement_pool,
            key=lambda movie: _complement_score(movie, filters=complement_filters),
        )
        total_runtime = primary.runtime + secondary.runtime
        return DoubleFeatureSelection(
            primary=primary,
            secondary=secondary,
            runtime_cap=runtime_cap,
            total_runtime=total_runtime,
        )

    return None


__all__ = ["DEFAULT_DOUBLE_FEATURE_RUNTIME", "DoubleFeatureSelection", "pick_double_feature"]
