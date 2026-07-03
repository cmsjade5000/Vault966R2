from __future__ import annotations

# Shared picker/filter helpers for FastAPI and UI clients.

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Query

from api.models.movie import Genre, Mood, Movie
from api.models.person import Person, Role
from api.utils.query_params import parse_optional_non_negative_int
from core.genres import search_terms_for_label

_ALLOWED_ORDERING = {
    "id_asc",
    "id_desc",
    "title_asc",
    "title_desc",
    "year_asc",
    "year_desc",
    "runtime_asc",
    "runtime_desc",
    "imdb_desc",
    "rt_desc",
    "flic",
    "random",
}

_MAX_SEARCH_QUERY_LENGTH = 200
_MAX_FILTER_LIST_RAW_LENGTH = 1000
_MAX_FILTER_ITEM_COUNT = 20
_MAX_FILTER_LABEL_LENGTH = 80


@dataclass(frozen=True)
class MovieFilterParams:
    q: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    runtime_min: Optional[int] = None
    runtime_max: Optional[int] = None
    genres: Tuple[str, ...] = ()
    moods: Tuple[str, ...] = ()
    order_by: str = "title_asc"

    def to_cookie_payload(self, *, page: Optional[int] = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "q": self.q,
            "genres": list(self.genres),
            "moods": list(self.moods),
            "year_min": self.year_min,
            "year_max": self.year_max,
            "runtime_min": self.runtime_min,
            "runtime_max": self.runtime_max,
            "order_by": self.order_by,
        }
        if page is not None:
            payload["page"] = page
        return payload


def _raise_bad_filter(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def _parse_list(value: Optional[Sequence[str] | str], field_name: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    items: list[str] = []
    if isinstance(value, str):
        if len(value) > _MAX_FILTER_LIST_RAW_LENGTH:
            _raise_bad_filter(
                f"{field_name} must be {_MAX_FILTER_LIST_RAW_LENGTH} characters or fewer"
            )
        raw_iterable: Iterable[str] = value.split(",")
    else:
        raw_iterable = value
    raw_count = 0
    for raw in raw_iterable:
        if raw is None:
            continue
        raw_count += 1
        if raw_count > _MAX_FILTER_ITEM_COUNT:
            _raise_bad_filter(f"{field_name} can include at most {_MAX_FILTER_ITEM_COUNT} values")
        candidate = str(raw).strip()
        if len(candidate) > _MAX_FILTER_LABEL_LENGTH:
            _raise_bad_filter(
                f"{field_name} values must be {_MAX_FILTER_LABEL_LENGTH} characters or fewer"
            )
        if candidate and candidate not in items:
            items.append(candidate)
    return tuple(items)


def parse_movie_filters(
    *,
    q: Optional[str],
    year_min: Optional[str | int],
    year_max: Optional[str | int],
    runtime_min: Optional[str | int],
    runtime_max: Optional[str | int],
    genres: Optional[Sequence[str] | str],
    moods: Optional[Sequence[str] | str],
    order_by: Optional[str],
) -> MovieFilterParams:
    if q is not None and len(q) > _MAX_SEARCH_QUERY_LENGTH:
        _raise_bad_filter(f"q must be {_MAX_SEARCH_QUERY_LENGTH} characters or fewer")
    clean_q = q.strip() if q else None
    clean_year_min = parse_optional_non_negative_int(year_min, "year_min")
    clean_year_max = parse_optional_non_negative_int(year_max, "year_max")
    clean_runtime_min = parse_optional_non_negative_int(runtime_min, "runtime_min")
    clean_runtime_max = parse_optional_non_negative_int(runtime_max, "runtime_max")
    clean_genres = _parse_list(genres, "genres")
    clean_moods = _parse_list(moods, "moods")
    clean_order = order_by or "title_asc"
    if clean_order not in _ALLOWED_ORDERING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order_by value",
        )
    if (
        clean_year_min is not None
        and clean_year_max is not None
        and clean_year_min > clean_year_max
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year_min cannot be greater than year_max",
        )
    if (
        clean_runtime_min is not None
        and clean_runtime_max is not None
        and clean_runtime_min > clean_runtime_max
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="runtime_min cannot be greater than runtime_max",
        )
    return MovieFilterParams(
        q=clean_q,
        year_min=clean_year_min,
        year_max=clean_year_max,
        runtime_min=clean_runtime_min,
        runtime_max=clean_runtime_max,
        genres=clean_genres,
        moods=clean_moods,
        order_by=clean_order,
    )


def _to_like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def apply_filters(query: Query, params: MovieFilterParams) -> Query:
    if params.q:
        pattern = _to_like_pattern(params.q)
        query = query.filter(
            or_(
                Movie.title.ilike(pattern, escape="\\"),
                Movie.vault_id.ilike(pattern, escape="\\"),
                Movie.imdb_id.ilike(pattern, escape="\\"),
                cast(Movie.year, String).ilike(pattern, escape="\\"),
                Movie.genres.any(Genre.name.ilike(pattern, escape="\\")),
                Movie.roles.any(Role.person.has(Person.name.ilike(pattern, escape="\\"))),
            )
        )
    for genre_name in params.genres:
        search_terms = search_terms_for_label(genre_name)
        if search_terms:
            expressions = [
                Genre.name.ilike(_to_like_pattern(term), escape="\\") for term in search_terms
            ]
            query = query.filter(Movie.genres.any(or_(*expressions)))
        else:
            query = query.filter(Movie.genres.any(Genre.name == genre_name))
    for mood_name in params.moods:
        query = query.filter(Movie.moods.any(Mood.name == mood_name))
    if params.year_min is not None:
        query = query.filter(Movie.year >= params.year_min)
    if params.year_max is not None:
        query = query.filter(Movie.year <= params.year_max)
    if params.runtime_min is not None:
        query = query.filter(Movie.runtime >= params.runtime_min)
    if params.runtime_max is not None:
        query = query.filter(Movie.runtime <= params.runtime_max)
    return query


def ordering_clause(order_by: str):
    mapping = {
        "id_asc": (Movie.vault_id.asc().nullslast(), Movie.id.asc()),
        "id_desc": (Movie.vault_id.desc().nullslast(), Movie.id.desc()),
        "title_asc": (Movie.title.asc(), Movie.id.asc()),
        "title_desc": (Movie.title.desc(), Movie.id.asc()),
        "year_asc": (Movie.year.asc().nullslast(), Movie.id.asc()),
        "year_desc": (Movie.year.desc().nullslast(), Movie.id.asc()),
        "runtime_asc": (Movie.runtime.asc().nullslast(), Movie.id.asc()),
        "runtime_desc": (Movie.runtime.desc().nullslast(), Movie.id.asc()),
        "imdb_desc": (Movie.imdb_rating.desc().nullslast(), Movie.id.asc()),
        "rt_desc": (Movie.rt_score.desc().nullslast(), Movie.id.asc()),
        "flic": None,
        "random": (func.random(), Movie.id.asc()),
    }
    return mapping[order_by]


__all__ = [
    "MovieFilterParams",
    "apply_filters",
    "ordering_clause",
    "parse_movie_filters",
]
