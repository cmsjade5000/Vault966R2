from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any, Dict, Iterator, List, Tuple

from sqlalchemy.orm import Query, Session

from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
from core.picker import PickerCandidate, calculate_flic_score


def _chunked(values: Iterable[int], *, chunk_size: int) -> Iterator[list[int]]:
    chunk: list[int] = []
    for value in values:
        chunk.append(value)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def rank_movie_ids_by_flic(
    db: Session,
    *,
    base_query: Query,
    filters: Dict[str, Any],
    chunk_size: int = 1000,
) -> List[Tuple[float, int]]:
    """Return [(score, movie_id)] for all movies in base_query, ordered by score desc."""

    id_query = base_query.with_entities(Movie.id).order_by(None).order_by(Movie.id.asc())
    scored: List[Tuple[float, int]] = []

    for chunk_rows in _chunked(
        (row[0] for row in id_query.yield_per(chunk_size)), chunk_size=chunk_size
    ):
        if not chunk_rows:
            continue

        base_rows = (
            db.query(Movie.id, Movie.year, Movie.runtime).filter(Movie.id.in_(chunk_rows)).all()
        )
        year_by_id: dict[int, int | None] = {row[0]: row[1] for row in base_rows}
        runtime_by_id: dict[int, int | None] = {row[0]: row[2] for row in base_rows}

        genres_by_id: dict[int, list[str]] = defaultdict(list)
        for movie_id, genre_name in (
            db.query(movie_genres.c.movie_id, Genre.name)
            .join(Genre, Genre.id == movie_genres.c.genre_id)
            .filter(movie_genres.c.movie_id.in_(chunk_rows))
            .all()
        ):
            if genre_name:
                genres_by_id[int(movie_id)].append(str(genre_name))

        moods_by_id: dict[int, list[str]] = defaultdict(list)
        for movie_id, mood_name in (
            db.query(movie_moods.c.movie_id, Mood.name)
            .join(Mood, Mood.id == movie_moods.c.mood_id)
            .filter(movie_moods.c.movie_id.in_(chunk_rows))
            .all()
        ):
            if mood_name:
                moods_by_id[int(movie_id)].append(str(mood_name))

        for movie_id in chunk_rows:
            candidate = PickerCandidate.from_iterables(
                genres=genres_by_id.get(movie_id),
                moods=moods_by_id.get(movie_id),
                runtime=runtime_by_id.get(movie_id),
                year=year_by_id.get(movie_id),
            ).to_payload()
            score, _ = calculate_flic_score(candidate, filters)
            scored.append((score, movie_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def fetch_movies_in_rank_order(
    db: Session,
    *,
    ranked_ids: Sequence[int],
    options: list[Any] | None = None,
) -> list[Movie]:
    if not ranked_ids:
        return []

    query = db.query(Movie).filter(Movie.id.in_(ranked_ids))
    if options:
        query = query.options(*options)
    movies = query.all()

    by_id = {movie.id: movie for movie in movies if movie.id is not None}
    return [by_id[movie_id] for movie_id in ranked_ids if movie_id in by_id]
