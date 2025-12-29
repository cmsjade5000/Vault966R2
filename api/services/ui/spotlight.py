from __future__ import annotations

import datetime
import random
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.utils.sampling import reorder_movies_by_id_sequence, sample_movie_ids


def _daily_seed(day: datetime.date | None = None) -> int:
    day = day or datetime.date.today()
    return int(day.strftime("%Y%m%d"))


def get_daily_spotlight_ids(db: Session, *, limit: int = 4) -> list[int]:
    query = db.query(Movie).filter(
        Movie.poster_url.isnot(None),
        Movie.poster_url != "",
        Movie.poster_url != "N/A",
    )
    total = query.with_entities(func.count(Movie.id)).scalar() or 0
    if total <= 0:
        return []
    rng = random.Random(_daily_seed())
    return sample_movie_ids(query, total=total, limit=limit, rng=rng)


def get_daily_spotlight_movies(db: Session, *, limit: int = 4) -> list[Movie]:
    ids = get_daily_spotlight_ids(db, limit=limit)
    if not ids:
        return []
    rows = db.query(Movie).filter(Movie.id.in_(ids)).all()
    return reorder_movies_by_id_sequence(rows, ids)


def _extract_labels(items: Iterable[object] | None) -> list[str]:
    if not items:
        return []
    labels: list[str] = []
    for item in items:
        if not item:
            continue
        if isinstance(item, str):
            labels.append(item)
            continue
        name = getattr(item, "name", None)
        if name:
            labels.append(name)
    return labels


def build_spotlight_reason(movie: object) -> str:
    imdb_rating = getattr(movie, "imdb_rating", None)
    if isinstance(imdb_rating, (int, float)) and imdb_rating >= 8.0:
        return f"IMDb {imdb_rating:.1f} standout."

    rt_score = getattr(movie, "rt_score", None)
    if isinstance(rt_score, (int, float)) and rt_score >= 90:
        return f"Rotten Tomatoes favorite at {rt_score}%."

    genres = _extract_labels(getattr(movie, "genres", None))
    if genres:
        return f"Spotlighted for its {genres[0]} energy."

    moods = _extract_labels(getattr(movie, "moods", None))
    if moods:
        return f"Picked for {moods[0]} vibes."

    year = getattr(movie, "year", None)
    if isinstance(year, int):
        current_year = datetime.date.today().year
        if year >= current_year - 5:
            return f"Recent standout from {year}."

    runtime = getattr(movie, "runtime", None)
    if isinstance(runtime, int) and runtime <= 95:
        return f"Tight runtime at {runtime} minutes."

    return "Today's spotlight pick."
