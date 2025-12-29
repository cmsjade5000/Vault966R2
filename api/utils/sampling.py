from __future__ import annotations

import random
from collections.abc import Sequence

from sqlalchemy.orm import Query

from api.models.movie import Movie


def sample_movie_ids(
    query: Query,
    *,
    total: int,
    limit: int,
    rng: random.Random | None = None,
) -> list[int]:
    if total <= 0 or limit <= 0:
        return []

    rng = rng or random.Random()
    k = min(limit, total)
    base = query.order_by(None).order_by(Movie.id.asc()).with_entities(Movie.id)

    if total <= 10_000:
        offsets = rng.sample(range(total), k=k)
    else:
        offsets = [rng.randrange(total) for _ in range(k * 2)]

    ids: list[int] = []
    seen: set[int] = set()
    for offset in offsets:
        movie_id = base.offset(offset).limit(1).scalar()
        if movie_id is None:
            continue
        movie_id = int(movie_id)
        if movie_id in seen:
            continue
        seen.add(movie_id)
        ids.append(movie_id)
        if len(ids) >= k:
            break

    return ids


def reorder_movies_by_id_sequence(movies: Sequence[Movie], ids: Sequence[int]) -> list[Movie]:
    by_id = {movie.id: movie for movie in movies if movie.id is not None}
    return [by_id[movie_id] for movie_id in ids if movie_id in by_id]
