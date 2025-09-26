from __future__ import annotations

import math
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload

from api.models.movie import Genre, Movie
from api.models.person import Person, Role
from api.schemas.movie_detail import (
    MovieDetail,
    PersonNested,
    RoleWithPersonRead,
    SimilarMovie,
)
from core.picker import calculate_flic_score
from core.poster_theme import select_poster_theme
from core.genres import split_and_normalize
from api.utils.providers import split_providers


def _fetch_movie(db: Session, movie_id: int) -> Optional[Movie]:
    return (
        db.query(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.moods),
            selectinload(Movie.roles).selectinload(Role.person),
        )
        .filter(Movie.id == movie_id)
        .one_or_none()
    )


def _build_roles(movie: Movie) -> List[RoleWithPersonRead]:
    roles_with_person = []
    for role in movie.roles:
        person: Person = role.person
        roles_with_person.append(
            RoleWithPersonRead(
                id=role.id,
                movie_id=role.movie_id,
                person_id=role.person_id,
                role_type=(
                    role.role_type.value
                    if hasattr(role.role_type, "value")
                    else str(role.role_type)
                ),
                character_name=role.character_name,
                billing_order=role.billing_order,
                person=PersonNested(
                    id=person.id,
                    name=person.name,
                    imdb_id=getattr(person, "imdb_id", None),
                    tmdb_id=getattr(person, "tmdb_id", None),
                ),
            )
        )
    roles_with_person.sort(
        key=lambda r: (
            r.billing_order is None,
            r.billing_order if r.billing_order is not None else math.inf,
            (r.person.name or "").lower(),
            r.person.id or 0,
        )
    )
    return roles_with_person


def _get_similarity_candidates(db: Session, movie: Movie) -> List[Movie]:
    genre_names = split_and_normalize([genre.name for genre in movie.genres])

    query = db.query(Movie).options(selectinload(Movie.genres), selectinload(Movie.moods))
    query = query.filter(Movie.id != movie.id)

    if genre_names:
        query = query.filter(Movie.genres.any(Genre.name.in_(genre_names)))

    return query.limit(100).all()


def _score_similar(movie: Movie, candidates: List[Movie]) -> List[SimilarMovie]:
    base_genres = set(split_and_normalize([genre.name for genre in movie.genres]))

    filters = {
        "genres": list(base_genres),
        "runtime_max": movie.runtime,
        "year_min": movie.year - 5 if movie.year else None,
        "year_max": movie.year + 5 if movie.year else None,
    }

    scored: List[SimilarMovie] = []
    for candidate in candidates:
        candidate_genres = set(split_and_normalize([genre.name for genre in candidate.genres]))
        shared_genres = len(base_genres & candidate_genres)
        if shared_genres < 1:
            continue

        candidate_payload = {
            "genres": list(candidate_genres),
            "runtime": candidate.runtime,
            "year": candidate.year,
        }
        score, _ = calculate_flic_score(candidate_payload, filters)
        scored.append(
            SimilarMovie(
                id=candidate.id,
                title=candidate.title,
                poster_url=candidate.poster_url,
                year=candidate.year,
                flic_score=score,
                poster_theme=select_poster_theme(list(candidate_genres)),
            )
        )

    scored.sort(
        key=lambda item: item.flic_score if item.flic_score is not None else 0.0,
        reverse=True,
    )

    if not scored:
        fallback = sorted(
            candidates,
            key=lambda c: (c.year or 0, c.id),
            reverse=True,
        )[:12]
        return [
            SimilarMovie(
                id=candidate.id,
                title=candidate.title,
                poster_url=candidate.poster_url,
                year=candidate.year,
                flic_score=None,
                poster_theme=select_poster_theme(
                    split_and_normalize([genre.name for genre in candidate.genres])
                ),
            )
            for candidate in fallback
        ]

    return scored[:12]


def get_movie_detail(db: Session, movie_id: int) -> Optional[MovieDetail]:
    movie = _fetch_movie(db, movie_id)
    if movie is None:
        return None

    roles = _build_roles(movie)
    where_to_watch = split_providers(movie.where_to_watch)

    similar_candidates = _get_similarity_candidates(db, movie)
    similar = _score_similar(movie, similar_candidates)

    detail = MovieDetail(
        id=movie.id,
        title=movie.title,
        year=movie.year,
        runtime=movie.runtime,
        plot=movie.plot,
        genres=split_and_normalize([genre.name for genre in movie.genres]),
        moods=[mood.name for mood in movie.moods],
        poster_url=movie.poster_url,
        backdrop_url=movie.backdrop_url,
        imdb_id=movie.imdb_id,
        tmdb_id=movie.tmdb_id,
        imdb_rating=movie.imdb_rating,
        imdb_votes=movie.imdb_votes,
        rt_score=movie.rt_score,
        where_to_watch=where_to_watch,
        languages=movie.languages,
        countries=movie.countries,
        collection=movie.collection,
        roles=roles,
        similar=similar,
        poster_theme=select_poster_theme([genre.name for genre in movie.genres]),
        flagged=movie.flag is not None,
    )
    return detail
