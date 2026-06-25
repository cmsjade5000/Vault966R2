from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from random import Random
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.movie import Genre, Movie, movie_genres
from api.models.profile import MoviePreference
from api.services.double_feature import DEFAULT_DOUBLE_FEATURE_RUNTIME, pick_double_feature
from api.services.profiles import (
    ensure_profile_cookie,
    get_active_profile_id,
    get_preferences_for_movies,
    get_profiles,
)
from api.services.ui.grid import attach_genre_display, attach_poster_themes
from api.services.ui.spotlight import build_spotlight_reason, get_daily_spotlight_movies
from api.services.ui.templates import TEMPLATES
from api.services.trusted_movies import get_untrusted_movie_ids, trusted_movie_query

router = APIRouter()

DISCOVER_TIME_ZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RailDefinition:
    key: str
    title: str
    description: str


RAIL_DEFINITIONS = (
    RailDefinition(
        "recently-added",
        "Recently Added",
        "The newest trusted Vault entries.",
    ),
    RailDefinition(
        "under-100",
        "Under 100 Minutes",
        "Shorter picks that still feel like a full movie night.",
    ),
    RailDefinition(
        "highly-rated",
        "Highly Rated",
        "Strong audience or critic scores with meaningful support.",
    ),
    RailDefinition(
        "hidden-gems",
        "Hidden Gems",
        "Well-liked titles outside the most heavily voted mainstream.",
    ),
    RailDefinition(
        "before-2000",
        "Before 2000",
        "Trusted favorites from the earlier shelves.",
    ),
    RailDefinition(
        "edition-cuts",
        "Edition Cuts",
        "Unrated, extended, director's cuts, and other named editions.",
    ),
)


def _with_poster(query):
    return query.filter(
        Movie.poster_url.isnot(None),
        Movie.poster_url != "",
        Movie.poster_url != "N/A",
    )


def _discover_day() -> date:
    return datetime.now(DISCOVER_TIME_ZONE).date()


def _stable_daily_rank(day: date, scope: str, stable_id: str) -> str:
    value = f"discover:v2|{day.isoformat()}|{scope}|{stable_id}"
    return sha256(value.encode("utf-8")).hexdigest()


def _stable_movie_id(movie: Movie) -> str:
    return movie.vault_id or f"movie-{movie.id}"


def _ordered_rail_definitions(day: date) -> list[RailDefinition]:
    return sorted(
        RAIL_DEFINITIONS,
        key=lambda rail: _stable_daily_rank(day, "rail-order", rail.key),
    )


def _rail_candidates(db: Session, key: str) -> list[Movie]:
    query = _with_poster(trusted_movie_query(db)).options(selectinload(Movie.genres))
    if key == "recently-added":
        return query.order_by(Movie.id.desc()).limit(80).all()
    if key == "under-100":
        query = query.filter(Movie.runtime.isnot(None), Movie.runtime <= 100)
    elif key == "highly-rated":
        query = query.filter(
            or_(
                (Movie.imdb_rating >= 7.5) & (Movie.imdb_votes >= 10_000),
                Movie.rt_score >= 85,
            )
        )
    elif key == "hidden-gems":
        query = query.filter(
            Movie.imdb_rating >= 6.8,
            Movie.imdb_votes.isnot(None),
            Movie.imdb_votes < 100_000,
        )
    elif key == "before-2000":
        query = query.filter(Movie.year.isnot(None), Movie.year < 2000)
    elif key == "edition-cuts":
        markers = (
            "%(Unrated)%",
            "%(Extended%",
            "%Director's Cut%",
            "%Special Edition%",
            "%Anniversary Edition%",
            "%Final Cut%",
        )
        query = query.filter(or_(*(Movie.title.ilike(marker) for marker in markers)))
    return query.all()


def _build_discover_rails(
    db: Session,
    *,
    used_ids: set[int],
    limit: int = 5,
    day: Optional[date] = None,
) -> list[dict[str, object]]:
    day = day or _discover_day()
    rails: list[dict[str, object]] = []
    for definition in _ordered_rail_definitions(day):
        candidates = sorted(
            _rail_candidates(db, definition.key),
            key=lambda movie: _stable_daily_rank(
                day,
                definition.key,
                _stable_movie_id(movie),
            ),
        )
        fresh = [movie for movie in candidates if movie.id is not None and movie.id not in used_ids]
        selected = fresh[:limit]
        if len(selected) < limit:
            selected_ids = {movie.id for movie in selected}
            selected.extend(
                movie
                for movie in candidates
                if movie.id is not None
                and movie.id not in used_ids
                and movie.id not in selected_ids
            )
            selected = selected[:limit]
        used_ids.update(movie.id for movie in selected if movie.id is not None)
        rails.append(
            {
                "key": definition.key,
                "title": definition.title,
                "description": definition.description,
                "movies": selected,
                "href": f"/ui/movies?preset={definition.key}&view=grid&page=1",
            }
        )
    return rails


def _top_imdb(
    db: Session,
    *,
    limit: int,
    exclude_ids: Optional[set[int]] = None,
) -> list[Movie]:
    query = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.imdb_rating.isnot(None))
        .order_by(
            Movie.imdb_rating.desc(),
            Movie.imdb_votes.desc().nullslast(),
            Movie.title.asc(),
        )
    )
    if exclude_ids:
        query = query.filter(~Movie.id.in_(exclude_ids))
    return query.limit(limit).all()


def _top_rt(
    db: Session,
    *,
    limit: int,
    exclude_ids: Optional[set[int]] = None,
) -> list[Movie]:
    query = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.rt_score.isnot(None))
        .order_by(
            Movie.rt_score.desc(),
            Movie.imdb_votes.desc().nullslast(),
            Movie.title.asc(),
        )
    )
    if exclude_ids:
        query = query.filter(~Movie.id.in_(exclude_ids))
    return query.limit(limit).all()


def _top_genre_names(db: Session, *, limit: int) -> list[str]:
    excluded_ids = get_untrusted_movie_ids(db)
    rows = (
        db.query(Genre.name, func.count().label("count"))
        .join(movie_genres, Genre.id == movie_genres.c.genre_id)
        .join(Movie, Movie.id == movie_genres.c.movie_id)
        .filter(~Movie.id.in_(excluded_ids) if excluded_ids else True)
        .group_by(Genre.name)
        .order_by(func.count().desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows if row[0]]


def _movie_genres(movie: Movie) -> list[str]:
    return [genre.name for genre in getattr(movie, "genres", []) if genre.name]


def _reason_tags_for_movie(
    movie: Movie,
    *,
    forced_tags: Optional[list[str]] = None,
    include_rating: bool = False,
) -> list[str]:
    tags: list[str] = []
    for tag in forced_tags or []:
        clean = tag.strip()
        if clean and clean not in tags:
            tags.append(clean)

    if include_rating:
        imdb_rating = movie.imdb_rating
        rt_score = movie.rt_score
        if imdb_rating is not None:
            tags.append(f"IMDb {imdb_rating:.1f}")
        elif rt_score is not None:
            tags.append(f"RT {rt_score}%")

    if len(tags) < 2:
        genres = _movie_genres(movie)
        if genres:
            tags.append(genres[0])

    return tags[:2]


def _pairing_reason_tags(primary: Movie, secondary: Movie, theme_label: Optional[str]) -> list[str]:
    tags: list[str] = []
    if theme_label:
        tags.append(theme_label)

    primary_genres = _movie_genres(primary)
    secondary_genres = _movie_genres(secondary)
    secondary_set = {label.lower() for label in secondary_genres}
    shared_genres = [label for label in primary_genres if label.lower() in secondary_set]
    if shared_genres and len(tags) < 2:
        tags.append(f"Shared {shared_genres[0]}")

    if len(tags) < 2:
        primary_rating = primary.imdb_rating or 0
        secondary_rating = secondary.imdb_rating or 0
        if primary_rating >= 7.8 and secondary_rating >= 7.8:
            tags.append("High rated")

    return tags[:2]


def _pick_selected_for_you(
    db: Session,
    profile_id: int,
    *,
    limit: int = 6,
    exclude_ids: Optional[set[int]] = None,
) -> tuple[list[Movie], list[str]]:
    if not profile_id:
        return [], []

    liked_movies = (
        db.query(Movie)
        .join(MoviePreference, MoviePreference.movie_id == Movie.id)
        .options(selectinload(Movie.genres))
        .filter(MoviePreference.profile_id == profile_id)
        .filter(MoviePreference.liked.is_(True))
        .order_by(desc(MoviePreference.updated_at), Movie.title.asc())
        .limit(24)
        .all()
    )
    if not liked_movies:
        return [], []

    preference_rows = (
        db.query(MoviePreference)
        .filter(MoviePreference.profile_id == profile_id)
        .filter(
            or_(
                MoviePreference.liked.is_(True),
                MoviePreference.watchlist.is_(True),
            )
        )
        .all()
    )
    preferred_ids = {preference.movie_id for preference in preference_rows}
    excluded = set(exclude_ids or set()) | preferred_ids

    genre_counts: dict[str, int] = {}
    for movie in liked_movies:
        for genre in getattr(movie, "genres", []) or []:
            name = getattr(genre, "name", None)
            if name:
                genre_counts[name] = genre_counts.get(name, 0) + 1

    top_genres = [
        name
        for name, _count in sorted(
            genre_counts.items(), key=lambda item: (-item[1], item[0].lower())
        )
    ][:3]
    if not top_genres:
        return [], []

    candidates = (
        _with_poster(trusted_movie_query(db))
        .options(selectinload(Movie.genres))
        .filter(Movie.genres.any(Genre.name.in_(top_genres)))
        .filter(or_(Movie.imdb_rating.isnot(None), Movie.rt_score.isnot(None)))
        .filter(~Movie.id.in_(excluded))
        .order_by(
            Movie.imdb_rating.desc().nullslast(),
            Movie.rt_score.desc().nullslast(),
            Movie.imdb_votes.desc().nullslast(),
            Movie.title.asc(),
        )
        .limit(limit * 4)
        .all()
    )

    selected: list[Movie] = []
    used_genres: set[str] = set()
    for movie in candidates:
        if movie.id is None or movie.id in excluded:
            continue
        genre_labels = _movie_genres(movie)
        primary = genre_labels[0].lower() if genre_labels else ""
        if primary and primary in used_genres:
            continue
        selected.append(movie)
        if primary:
            used_genres.add(primary)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        selected_ids = {movie.id for movie in selected if movie.id is not None}
        for movie in candidates:
            if movie.id is None or movie.id in excluded or movie.id in selected_ids:
                continue
            selected.append(movie)
            if len(selected) >= limit:
                break

    return selected, top_genres


def _personalized_reason(movie: Movie, preferred_genres: list[str]) -> str:
    movie_genres = {genre.lower(): genre for genre in _movie_genres(movie)}
    for genre in preferred_genres:
        if genre.lower() in movie_genres:
            return f"Because you like {movie_genres[genre.lower()]}"
    if movie.imdb_rating is not None:
        return f"IMDb {movie.imdb_rating:.1f} match"
    if movie.rt_score is not None:
        return f"RT {movie.rt_score}% match"
    return "Matches your recent likes"


def _pick_genre_spotlights(
    db: Session,
    genre_names: Iterable[str],
    used_ids: set[int],
    *,
    seed: Optional[int] = None,
    pool_size: int = 6,
) -> list[dict[str, object]]:
    spotlights: list[dict[str, object]] = []
    base_rng = Random(seed) if seed is not None else None
    for genre_name in genre_names:
        genre_rng = Random((seed or 0) + len(spotlights)) if base_rng else None
        query = (
            _with_poster(trusted_movie_query(db))
            .options(selectinload(Movie.genres))
            .filter(Movie.genres.any(Genre.name == genre_name))
            .filter(or_(Movie.imdb_rating.isnot(None), Movie.rt_score.isnot(None)))
        )
        if used_ids:
            query = query.filter(~Movie.id.in_(used_ids))
        candidates = (
            query.order_by(
                Movie.imdb_rating.desc().nullslast(),
                Movie.rt_score.desc().nullslast(),
                Movie.imdb_votes.desc().nullslast(),
                Movie.title.asc(),
            )
            .limit(pool_size)
            .all()
        )
        if not candidates:
            continue
        movie = candidates[0] if not genre_rng else genre_rng.choice(candidates)
        if not movie or movie.id is None:
            continue
        used_ids.add(movie.id)
        spotlights.append({"genre": genre_name, "movie": movie})
    return spotlights


def _pick_pairings(
    db: Session,
    genre_names: list[str],
    used_ids: set[int],
    *,
    limit: int = 3,
    seed: Optional[int] = None,
) -> list[object]:
    pairings: list[object] = []
    seen_pairs: set[tuple[int, int]] = set()
    if seed is None:
        seeds = [7, 19, 31, 47]
    else:
        rng = Random(seed)
        seeds = [rng.randint(1, 1000000) for _ in range(limit + 2)]

    def register(selection) -> None:
        primary_id = getattr(selection.primary, "id", None)
        secondary_id = getattr(selection.secondary, "id", None)
        if primary_id is None or secondary_id is None:
            return
        key = tuple(sorted((primary_id, secondary_id)))
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        used_ids.update({primary_id, secondary_id})
        pairings.append(selection)

    for idx, genre_name in enumerate(genre_names[: limit + 1]):
        selection = pick_double_feature(
            db,
            runtime_cap=DEFAULT_DOUBLE_FEATURE_RUNTIME,
            genre=genre_name,
            seed=seeds[idx % len(seeds)],
            require_poster=True,
        )
        if selection:
            register(selection)
        if len(pairings) >= limit:
            break

    if len(pairings) < limit:
        selection = pick_double_feature(
            db,
            runtime_cap=DEFAULT_DOUBLE_FEATURE_RUNTIME,
            seed=seeds[-1],
            require_poster=True,
        )
        if selection:
            register(selection)

    return pairings


def _discover_movie_payload(movie: Movie, reasons: list[str]) -> dict:
    return {
        "id": movie.id,
        "title": movie.title,
        "year": movie.year,
        "poster_url": movie.poster_url,
        "poster_theme": getattr(movie, "poster_theme", None),
        "liked": getattr(movie, "liked", False),
        "watchlist": getattr(movie, "watchlist", False),
        "reasons": reasons,
    }


@router.get("/api/discover/refresh")
def discover_refresh(
    request: Request,
    db: Session = Depends(get_db),
    seed: Optional[int] = Query(default=None, ge=1, le=2_000_000_000),
    pairings_limit: int = Query(default=2, ge=1, le=4),
    genre_limit: int = Query(default=6, ge=3, le=12),
) -> dict:
    top_genres = _top_genre_names(db, limit=genre_limit)

    used_ids: set[int] = set()
    pairings = _pick_pairings(
        db,
        top_genres,
        used_ids,
        limit=pairings_limit,
        seed=seed,
    )
    genre_spotlights = _pick_genre_spotlights(
        db,
        top_genres,
        used_ids,
        seed=seed,
    )

    pairing_reasons: dict[str, list[str]] = {}
    discover_reasons: dict[int, list[str]] = {}
    for pairing in pairings:
        primary_id = getattr(pairing.primary, "id", None)
        secondary_id = getattr(pairing.secondary, "id", None)
        if primary_id is None or secondary_id is None:
            continue
        key = f"{primary_id}-{secondary_id}"
        pairing_reasons[key] = _pairing_reason_tags(
            pairing.primary, pairing.secondary, pairing.theme_label
        )
        discover_reasons[primary_id] = _reason_tags_for_movie(pairing.primary, include_rating=True)
        discover_reasons[secondary_id] = _reason_tags_for_movie(
            pairing.secondary, include_rating=True
        )

    for item in genre_spotlights:
        movie = item.get("movie")
        genre = item.get("genre")
        if isinstance(movie, Movie) and movie.id is not None and isinstance(genre, str):
            discover_reasons[movie.id] = _reason_tags_for_movie(
                movie, forced_tags=[genre], include_rating=True
            )

    all_movies: dict[int, Movie] = {}
    for item in genre_spotlights:
        movie = item.get("movie")
        if isinstance(movie, Movie) and movie.id is not None:
            all_movies[movie.id] = movie
    for pairing in pairings:
        for movie in (pairing.primary, pairing.secondary):
            if movie.id is not None:
                all_movies[movie.id] = movie

    attach_poster_themes(all_movies.values())

    active_profile_id = get_active_profile_id(request, db)
    preferences = get_preferences_for_movies(db, active_profile_id, all_movies.keys())
    for movie in all_movies.values():
        pref = preferences.get(movie.id or 0, {})
        setattr(movie, "liked", pref.get("liked", False))
        setattr(movie, "watchlist", pref.get("watchlist", False))

    pairing_payloads = []
    for pairing in pairings:
        primary = pairing.primary
        secondary = pairing.secondary
        if primary.id is None or secondary.id is None:
            continue
        key = f"{primary.id}-{secondary.id}"
        pairing_payloads.append(
            {
                "primary": _discover_movie_payload(primary, discover_reasons.get(primary.id, [])),
                "secondary": _discover_movie_payload(
                    secondary, discover_reasons.get(secondary.id, [])
                ),
                "theme_label": pairing.theme_label,
                "total_runtime": pairing.total_runtime,
                "pairing_reasons": pairing_reasons.get(key, []),
            }
        )

    genre_payloads = []
    for item in genre_spotlights:
        movie = item.get("movie")
        genre = item.get("genre")
        if isinstance(movie, Movie) and movie.id is not None and isinstance(genre, str):
            genre_payloads.append(
                {
                    "genre": genre,
                    "movie": _discover_movie_payload(movie, discover_reasons.get(movie.id, [])),
                }
            )

    return {
        "pairings": pairing_payloads,
        "genre_spotlights": genre_payloads,
    }


@router.get("/ui/discover", response_class=HTMLResponse)
def discover(request: Request, db: Session = Depends(get_db)):
    profiles = get_profiles(db)
    active_profile_id = get_active_profile_id(request, db)

    spotlight_movies = get_daily_spotlight_movies(db, limit=4)

    used_ids = {movie.id for movie in spotlight_movies if movie.id is not None}
    selected_for_you, selected_for_you_genres = _pick_selected_for_you(
        db,
        active_profile_id,
        exclude_ids=used_ids,
    )
    used_ids.update(movie.id for movie in selected_for_you if movie.id is not None)

    rails = _build_discover_rails(db, used_ids=used_ids)
    spotlight_reasons = {
        movie.id: build_spotlight_reason(movie)
        for movie in spotlight_movies
        if movie.id is not None
    }
    selected_for_you_reasons = {
        movie.id: _personalized_reason(movie, selected_for_you_genres)
        for movie in selected_for_you
        if movie.id is not None
    }

    all_movies: dict[int, Movie] = {}
    for movie in spotlight_movies:
        if movie.id is not None:
            all_movies[movie.id] = movie
    for movie in selected_for_you:
        if movie.id is not None:
            all_movies[movie.id] = movie
    for rail in rails:
        for movie in rail["movies"]:
            if movie.id is not None:
                all_movies[movie.id] = movie
    attach_poster_themes(all_movies.values())
    attach_genre_display(all_movies.values())

    preferences = get_preferences_for_movies(db, active_profile_id, all_movies.keys())
    for movie in all_movies.values():
        pref = preferences.get(movie.id or 0, {})
        setattr(movie, "liked", pref.get("liked", False))
        setattr(movie, "watchlist", pref.get("watchlist", False))

    context = {
        "request": request,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
        "spotlight_movies": spotlight_movies,
        "spotlight_lead": spotlight_movies[0] if spotlight_movies else None,
        "spotlight_supporting": spotlight_movies[1:],
        "spotlight_reasons": spotlight_reasons,
        "selected_for_you": selected_for_you,
        "selected_for_you_genres": selected_for_you_genres,
        "selected_for_you_reasons": selected_for_you_reasons,
        "rails": rails,
    }
    response = TEMPLATES.TemplateResponse(request, "movies_discover.html", context)
    ensure_profile_cookie(request, response, db)
    return response
