from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from api.models.flic_memory import FlicMemory
from api.models.movie import Genre, Mood, Movie
from core.picker import pick_movie as select_movie


class MovieSelectionError(Exception):
    """Raised when a movie cannot be selected for the given filters."""


def _record_selection(db: Session, movie_id: int, keep_last: int = 10) -> None:
    db.add(FlicMemory(movie_id=movie_id))
    db.flush()
    ids_to_remove = (
        db.query(FlicMemory.id)
        .order_by(FlicMemory.created_at.desc(), FlicMemory.id.desc())
        .offset(keep_last)
        .all()
    )
    if ids_to_remove:
        db.query(FlicMemory).filter(FlicMemory.id.in_([row[0] for row in ids_to_remove])).delete(
            synchronize_session=False
        )
    db.commit()


def pick_movie(
    db: Session,
    *,
    mood: Optional[str],
    genre: Optional[str],
    year_min: Optional[int],
    year_max: Optional[int],
    runtime_max: Optional[int],
) -> Movie:
    query = (
        db.query(Movie)
        .options(selectinload(Movie.genres), selectinload(Movie.moods))
        .order_by(Movie.title.asc())
    )
    if genre:
        query = query.filter(Movie.genres.any(Genre.name == genre))
    if year_min is not None:
        query = query.filter(Movie.year >= year_min)
    if year_max is not None:
        query = query.filter(Movie.year <= year_max)
    if runtime_max is not None:
        query = query.filter(Movie.runtime <= runtime_max)
    if mood:
        query = query.filter(Movie.moods.any(Mood.name == mood))

    movies = query.all()
    if not movies:
        raise MovieSelectionError("No movies found for the given filters")

    filters: Dict[str, Optional[int] | List[str]] = {
        "moods": [mood] if mood else [],
        "genres": [genre] if genre else [],
        "year_min": year_min,
        "year_max": year_max,
        "runtime_max": runtime_max,
    }

    candidates = []
    for movie in movies:
        candidates.append(
            {
                "id": movie.id,
                "movie": movie,
                "moods": [m.name for m in movie.moods],
                "genres": [g.name for g in movie.genres],
                "runtime": movie.runtime,
                "year": movie.year,
            }
        )

    selection = select_movie(candidates, filters=filters)
    if selection is None:
        raise MovieSelectionError("No movies available")

    selected_movie = selection.get("movie")
    if selected_movie is None:
        selected_movie = next((movie for movie in movies if movie.id == selection.get("id")), None)
    if selected_movie is None:
        raise MovieSelectionError("No movies available")

    if selected_movie.id is not None:
        _record_selection(db, selected_movie.id)

    setattr(selected_movie, "flagged", selected_movie.flag is not None)
    return selected_movie


__all__ = ["MovieSelectionError", "pick_movie"]
