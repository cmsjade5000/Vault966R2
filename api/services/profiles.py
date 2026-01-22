from __future__ import annotations

from typing import Dict, Iterable, List

from fastapi import Request, Response
from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.models.profile import MoviePreference, Profile

PROFILE_COOKIE_NAME = "vault_profile_id"
PROFILE_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _ensure_default_profiles(db: Session) -> List[Profile]:
    profiles = db.query(Profile).order_by(Profile.id.asc()).all()
    if profiles:
        return profiles
    defaults = [Profile(name="User A"), Profile(name="User B")]
    db.add_all(defaults)
    db.commit()
    return db.query(Profile).order_by(Profile.id.asc()).all()


def get_profiles(db: Session) -> List[Profile]:
    return _ensure_default_profiles(db)


def get_active_profile_id(request: Request, db: Session) -> int:
    profiles = _ensure_default_profiles(db)
    if not profiles:
        return 0
    raw = request.cookies.get(PROFILE_COOKIE_NAME)
    if raw:
        try:
            profile_id = int(raw)
        except ValueError:
            profile_id = 0
        if any(profile.id == profile_id for profile in profiles):
            return profile_id
    return profiles[0].id


def set_active_profile_cookie(response: Response, profile_id: int) -> None:
    response.set_cookie(
        PROFILE_COOKIE_NAME,
        str(profile_id),
        max_age=PROFILE_COOKIE_MAX_AGE,
        samesite="lax",
        httponly=False,
    )


def ensure_profile_cookie(request: Request, response: Response, db: Session) -> int:
    profile_id = get_active_profile_id(request, db)
    if request.cookies.get(PROFILE_COOKIE_NAME) != str(profile_id):
        set_active_profile_cookie(response, profile_id)
    return profile_id


def get_preferences_for_movies(
    db: Session,
    profile_id: int,
    movie_ids: Iterable[int],
) -> Dict[int, Dict[str, bool]]:
    ids = [movie_id for movie_id in movie_ids if movie_id is not None]
    if not ids:
        return {}
    rows = (
        db.query(MoviePreference)
        .filter(MoviePreference.profile_id == profile_id)
        .filter(MoviePreference.movie_id.in_(ids))
        .all()
    )
    return {
        pref.movie_id: {
            "liked": bool(pref.liked),
            "watchlist": bool(pref.watchlist),
        }
        for pref in rows
    }


def update_movie_preference(
    db: Session,
    *,
    profile_id: int,
    movie_id: int,
    liked: bool | None = None,
    watchlist: bool | None = None,
) -> MoviePreference | None:
    pref = (
        db.query(MoviePreference)
        .filter(MoviePreference.profile_id == profile_id)
        .filter(MoviePreference.movie_id == movie_id)
        .one_or_none()
    )
    if pref is None and liked is None and watchlist is None:
        return None

    if pref is None:
        pref = MoviePreference(
            profile_id=profile_id,
            movie_id=movie_id,
            liked=bool(liked),
            watchlist=bool(watchlist),
        )
        db.add(pref)
        db.commit()
        return pref

    if liked is not None:
        pref.liked = liked
    if watchlist is not None:
        pref.watchlist = watchlist

    if not pref.liked and not pref.watchlist:
        db.delete(pref)
        db.commit()
        return None

    db.commit()
    return pref


def get_watchlist_movies(db: Session, *, profile_id: int) -> List[Movie]:
    return (
        db.query(Movie)
        .join(MoviePreference, MoviePreference.movie_id == Movie.id)
        .filter(MoviePreference.profile_id == profile_id)
        .filter(MoviePreference.watchlist.is_(True))
        .all()
    )


__all__ = [
    "PROFILE_COOKIE_NAME",
    "get_profiles",
    "get_active_profile_id",
    "ensure_profile_cookie",
    "set_active_profile_cookie",
    "get_preferences_for_movies",
    "update_movie_preference",
    "get_watchlist_movies",
]
