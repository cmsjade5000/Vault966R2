from __future__ import annotations

import datetime
import random
from typing import Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config import settings
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
    rng = random.Random() if settings.spotlight_rotate else random.Random(_daily_seed())
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


def _pick_spotlight_line(movie_id: int | None, options: List[str]) -> str:
    if not options:
        return "Today's spotlight pick."
    seed = _daily_seed() + (movie_id or 0)
    rng = random.Random(seed)
    return rng.choice(options)


def build_spotlight_reason(movie: object) -> str:
    movie_id = getattr(movie, "id", None)
    candidates: List[str] = []

    imdb_rating = getattr(movie, "imdb_rating", None)
    if isinstance(imdb_rating, (int, float)) and imdb_rating >= 8.0:
        candidates.extend(
            [
                f"Featured for its IMDb {imdb_rating:.1f} rating.",
                f"IMDb {imdb_rating:.1f} favorite in today's lineup.",
                f"Critics love this one—IMDb {imdb_rating:.1f}.",
            ]
        )

    rt_score = getattr(movie, "rt_score", None)
    if isinstance(rt_score, (int, float)) and rt_score >= 90:
        candidates.extend(
            [
                f"Featured with a {rt_score}% Rotten Tomatoes score.",
                f"A {rt_score}% Rotten Tomatoes crowd-pleaser.",
                f"Rotten Tomatoes darling at {rt_score}%.",
            ]
        )

    genres = _extract_labels(getattr(movie, "genres", None))
    if genres:
        primary = genres[0]
        secondary = genres[1] if len(genres) > 1 else None
        if secondary:
            candidates.extend(
                [
                    f"A {primary} pick with a touch of {secondary}.",
                    f"{primary} vibes with a hint of {secondary}.",
                    f"Leading with {primary} energy, edged by {secondary}.",
                ]
            )
        candidates.extend(
            [
                f"In the spotlight for its {primary} energy.",
                f"A fresh {primary} highlight today.",
                f"Spotlighted for its {primary} style.",
            ]
        )

    moods = _extract_labels(getattr(movie, "moods", None))
    if moods:
        mood = moods[0]
        candidates.extend(
            [
                f"Picked for its {mood} mood.",
                f"Chosen to match a {mood} night.",
                f"A {mood} pick for the queue.",
            ]
        )

    year = getattr(movie, "year", None)
    if isinstance(year, int):
        current_year = datetime.date.today().year
        if year >= current_year - 5:
            candidates.extend(
                [
                    f"A recent standout from {year}.",
                    f"A modern favorite from {year}.",
                    f"Fresh release highlight from {year}.",
                ]
            )
        elif year <= current_year - 25:
            candidates.extend(
                [
                    f"A vault classic from {year}.",
                    f"Throwback spotlight from {year}.",
                    f"A classic pick from {year}.",
                ]
            )

    runtime = getattr(movie, "runtime", None)
    if isinstance(runtime, int) and runtime <= 95:
        candidates.extend(
            [
                f"Spotlighted for a tight {runtime}-minute runtime.",
                f"Short and punchy at {runtime} minutes.",
                f"Quick watch clocking {runtime} minutes.",
            ]
        )
    elif isinstance(runtime, int) and runtime >= 150:
        candidates.extend(
            [
                f"An epic-length pick at {runtime} minutes.",
                f"Long-form favorite with {runtime} minutes to spare.",
                f"A big-screen marathon at {runtime} minutes.",
            ]
        )

    awards = getattr(movie, "awards", None)
    if isinstance(awards, str) and awards.strip():
        candidates.extend(
            [
                "Spotlighted for its award recognition.",
                "An award-season standout from the vault.",
                "Picked for its award buzz.",
            ]
        )

    collection = getattr(movie, "collection", None)
    if isinstance(collection, str) and collection.strip():
        collection_name = collection.strip()
        candidates.extend(
            [
                f"From the {collection_name} collection.",
                f"A highlight from the {collection_name} collection.",
            ]
        )

    return _pick_spotlight_line(movie_id, candidates)
