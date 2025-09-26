from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.models.movie import Genre, Movie
from core.genres import split_and_normalize


@dataclass
class CuratedCollection:
    key: str
    title: str
    description: str
    movies: Sequence[Movie]


@dataclass
class CollectionHealth:
    missing_runtime: int
    missing_plot: int
    missing_poster: int
    missing_provider: int
    avg_runtime: float | None
    genre_gaps: List[str]


def _run_base_query(db: Session):
    return db.query(Movie).options(
        selectinload(Movie.genres),
        selectinload(Movie.moods),
    )


def _first_n(query, limit: int) -> List[Movie]:
    return query.limit(limit).all()


def _genre_filter(query, genres: Iterable[str]):
    normalized = split_and_normalize(genres)
    if not normalized:
        return query
    return query.filter(Movie.genres.any(Genre.name.in_(normalized)))


def get_curated_collections(
    db: Session, *, items_per_collection: int = 8
) -> List[CuratedCollection]:
    collections: List[CuratedCollection] = []

    quick_hits = _first_n(
        _run_base_query(db)
        .filter(Movie.runtime.isnot(None))
        .filter(Movie.runtime <= 95)
        .order_by(Movie.runtime.asc(), Movie.year.desc()),
        items_per_collection,
    )
    if quick_hits:
        collections.append(
            CuratedCollection(
                key="quick_hits",
                title="Quick Hits",
                description="Crowd-pleasers under 95 minutes when you just want a vibe.",
                movies=quick_hits,
            )
        )

    epic_nights = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.runtime.isnot(None))
            .filter(Movie.runtime >= 140)
            .order_by(Movie.year.desc(), Movie.runtime.desc()),
            ["Adventure", "Epic", "Science Fiction", "Drama"],
        ),
        items_per_collection,
    )
    if epic_nights:
        collections.append(
            CuratedCollection(
                key="epic_night",
                title="Epic Night In",
                description="Big-screen energy—long runtimes, huge stakes, killer scores.",
                movies=epic_nights,
            )
        )

    comfort_nineties = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.year >= 1990)
            .filter(Movie.year <= 1999)
            .order_by(Movie.year.asc(), Movie.title.asc()),
            ["Comedy", "Romance"],
        ),
        items_per_collection,
    )
    if comfort_nineties:
        collections.append(
            CuratedCollection(
                key="comfort_90s",
                title="Comfort 90s",
                description="Feel-good rewatches from the VHS shelf—comfort food for the brain.",
                movies=comfort_nineties,
            )
        )

    documentary_focus = _first_n(
        _genre_filter(
            _run_base_query(db).order_by(Movie.year.desc(), Movie.title.asc()),
            ["Documentary"],
        ),
        items_per_collection,
    )
    if documentary_focus:
        collections.append(
            CuratedCollection(
                key="docs",
                title="Documentary Deep Dive",
                description="Real stories, reflective tones, and the truth-is-stranger moments.",
                movies=documentary_focus,
            )
        )

    high_energy = _first_n(
        _genre_filter(
            _run_base_query(db)
            .filter(Movie.runtime.isnot(None))
            .filter(Movie.runtime <= 120)
            .order_by(Movie.year.desc()),
            ["Action", "Thriller"],
        ),
        items_per_collection,
    )
    if high_energy:
        collections.append(
            CuratedCollection(
                key="high_energy",
                title="High Energy",
                description="Adrenaline-forward picks with tight runtimes and bold moves.",
                movies=high_energy,
            )
        )

    return collections


def get_collection_health(db: Session) -> CollectionHealth:
    base_query = db.query(Movie)

    missing_runtime = base_query.filter(Movie.runtime.is_(None)).count()
    missing_plot = base_query.filter(or_(Movie.plot.is_(None), Movie.plot == "")).count()
    missing_poster = base_query.filter(
        or_(Movie.poster_url.is_(None), Movie.poster_url == "")
    ).count()
    missing_provider = base_query.filter(
        or_(Movie.where_to_watch.is_(None), Movie.where_to_watch == "")
    ).count()

    avg_runtime = db.query(func.avg(Movie.runtime)).filter(Movie.runtime.isnot(None)).scalar()
    avg_runtime = float(avg_runtime) if avg_runtime is not None else None

    genre_counts = func.count(Movie.id)
    top_genres = (
        db.query(Genre.name, genre_counts)
        .select_from(Movie)
        .join(Movie.genres)
        .group_by(Genre.name)
        .order_by(genre_counts.desc())
        .limit(5)
        .all()
    )

    genre_gaps: List[str] = []
    if top_genres:
        seen = {name.lower() for name, _ in top_genres}
        aspirational = ["Animation", "Mystery", "Noir", "Western", "Family"]
        genre_gaps = [label for label in aspirational if label.lower() not in seen][:3]

    return CollectionHealth(
        missing_runtime=missing_runtime,
        missing_plot=missing_plot,
        missing_poster=missing_poster,
        missing_provider=missing_provider,
        avg_runtime=avg_runtime,
        genre_gaps=genre_gaps,
    )


__all__ = [
    "CollectionHealth",
    "CuratedCollection",
    "get_curated_collections",
    "get_collection_health",
]
