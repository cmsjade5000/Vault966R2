from __future__ import annotations

import json
import random
from typing import Iterable

from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.flic_preset import FlicPreset
from api.models.movie import Genre, Movie, movie_genres
from core.genres import split_and_normalize
from core.poster_theme import select_poster_theme

FILTER_COOKIE_NAME = "movies:lastFilters"
FILTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def load_filter_cookie(request: Request) -> dict[str, object]:
    raw = request.cookies.get(FILTER_COOKIE_NAME)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def dump_filter_cookie(payload: dict[str, object]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def query_library_stats(db: Session) -> dict[str, object]:
    total = db.query(func.count(Movie.id)).scalar() or 0
    avg_year_value = db.query(func.avg(Movie.year)).filter(Movie.year.isnot(None)).scalar()
    avg_year = int(round(avg_year_value)) if avg_year_value is not None else None
    top_genre = (
        db.query(Genre.name, func.count().label("count"))
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(Movie, Movie.id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .order_by(func.count().desc())
        .first()
    )

    return {
        "total": total,
        "average_year": avg_year,
        "top_genre": top_genre[0] if top_genre else "—",
    }


def get_taglines() -> tuple[list[str], str]:
    taglines = [
        "Your movie buddy—let’s find a vibe.",
        "Shortlist in two taps.",
        "Prefer surprises? I’ve got you.",
    ]
    return taglines, random.choice(taglines)


def get_built_in_presets() -> list[dict[str, object]]:
    return [
        {
            "name": "Fresh Favorites",
            "filters": {
                "year_min": 2018,
                "order_by": "year_desc",
                "runtime_max": 150,
            },
            "description": "Recently released crowd-pleasers",
        },
        {
            "name": "Family Night",
            "filters": {
                "genres": ["Animation", "Family"],
                "runtime_max": 110,
                "order_by": "title_asc",
            },
            "description": "Bright picks under two hours for all ages",
        },
        {
            "name": "Quick Thrills",
            "filters": {
                "genres": ["Action", "Thriller"],
                "runtime_max": 110,
                "order_by": "flic",
            },
            "description": "High-energy action under two hours",
        },
        {
            "name": "Comfort 90s",
            "filters": {
                "genres": ["Comedy", "Romance"],
                "year_min": 1990,
                "year_max": 1999,
                "order_by": "title_asc",
            },
            "description": "Feel-good comedies and rom-coms from the 90s",
        },
        {
            "name": "Sci-Fi Epics",
            "filters": {
                "genres": ["Science Fiction", "Adventure"],
                "runtime_max": 185,
                "order_by": "flic",
            },
            "description": "Big-scale sci-fi adventures with high stakes",
        },
        {
            "name": "Docs & Truth",
            "filters": {
                "genres": ["Documentary"],
                "order_by": "year_desc",
            },
            "description": "Recent documentaries with reflective tones",
        },
        {
            "name": "Indie Darlings",
            "filters": {
                "runtime_max": 115,
                "order_by": "flic",
            },
            "description": "Festival favorites with introspective vibes",
        },
    ]


def serialize_user_presets(db: Session) -> list[dict[str, object]]:
    user_presets = db.query(FlicPreset).order_by(FlicPreset.created_at.desc()).all()
    return [
        {
            "id": preset.id,
            "name": preset.name,
            "filters": preset.filters,
        }
        for preset in user_presets
    ]


def get_genre_options(db: Session) -> list[str]:
    raw_genres = [row[0] for row in db.query(Genre.name).order_by(Genre.name.asc()).all() if row[0]]
    return [
        label
        for label in sorted(split_and_normalize(raw_genres), key=str.casefold)
        if label.lower() not in {"tv movie", "nan"}
    ]


def get_decade_options(db: Session) -> list[dict[str, int]]:
    year_values = [
        row[0]
        for row in db.query(func.distinct(Movie.year)).filter(Movie.year.isnot(None)).all()
        if row[0]
    ]
    if not year_values:
        return []

    min_decade = (min(year_values) // 10) * 10
    max_decade = (max(year_values) // 10) * 10
    return [
        {
            "label": f"{decade}s",
            "start": decade,
            "end": decade + 9,
        }
        for decade in range(min_decade, max_decade + 1, 10)
    ]


def get_runtime_presets() -> list[dict[str, int | None]]:
    return [
        {"label": "Any", "value": None},
        {"label": "≤ 90 min", "value": 90},
        {"label": "≤ 120 min", "value": 120},
        {"label": "≤ 150 min", "value": 150},
        {"label": "≤ 180 min", "value": 180},
    ]


def attach_poster_themes(movies: Iterable[Movie]) -> None:
    for movie in movies:
        try:
            genre_names = [
                getattr(genre, "name", None) or "" for genre in getattr(movie, "genres", [])
            ]
        except TypeError:
            genre_names = []
        poster_theme = select_poster_theme(genre_names)
        setattr(movie, "poster_theme", poster_theme)


__all__ = [
    "FILTER_COOKIE_NAME",
    "FILTER_COOKIE_MAX_AGE",
    "load_filter_cookie",
    "dump_filter_cookie",
    "query_library_stats",
    "get_taglines",
    "get_built_in_presets",
    "serialize_user_presets",
    "get_genre_options",
    "get_decade_options",
    "get_runtime_presets",
    "attach_poster_themes",
]
