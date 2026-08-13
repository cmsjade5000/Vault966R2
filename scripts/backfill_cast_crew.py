#!/usr/bin/env python3
"""Backfill cast & crew into the roles table using TMDb."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

import httpx
from sqlalchemy import select

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from api.config import settings  # noqa: E402
from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie  # noqa: E402
from api.models.person import Person, Role, RoleType  # noqa: E402
from api.utils.provider_errors import run_provider_cli  # noqa: E402

TMDB_BASE = "https://api.themoviedb.org/3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cast & crew into roles using TMDb.")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry run).")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of movies processed.")
    parser.add_argument("--tmdb-key", help="TMDb API key (default: env TMDB_API_KEY or settings).")
    return parser.parse_args()


def fetch_tmdb_credits(client: httpx.Client, api_key: str, tmdb_id: int) -> dict | None:
    resp = client.get(
        f"{TMDB_BASE}/movie/{tmdb_id}/credits", params={"api_key": api_key}, timeout=12.0
    )
    if resp.status_code != 200:
        return None
    payload = resp.json()
    return payload if isinstance(payload, dict) else None


def upsert_person(db, name: str, tmdb_id: Optional[int], imdb_id: Optional[str]) -> int:
    if not name:
        raise ValueError("person name required")
    stmt = select(Person).where(Person.name == name)
    if tmdb_id is not None:
        stmt = stmt.where(Person.tmdb_id == tmdb_id)
    person = db.execute(stmt).scalars().first()
    if person is None:
        person = Person(name=name, tmdb_id=tmdb_id, imdb_id=imdb_id)
        db.add(person)
        db.flush()
    else:
        if tmdb_id and not person.tmdb_id:
            person.tmdb_id = tmdb_id
        if imdb_id and not person.imdb_id:
            person.imdb_id = imdb_id
    return person.id


def main() -> int:
    args = parse_args()
    api_key = args.tmdb_key or os.getenv("TMDB_API_KEY") or settings.tmdb_api_key
    if not api_key:
        raise SystemExit("TMDB_API_KEY is required.")

    updated = 0
    skipped = 0
    missing = 0
    errors = 0

    with SessionLocal() as db, httpx.Client() as client:
        query = db.query(Movie).filter(Movie.tmdb_id.isnot(None))
        if args.limit:
            query = query.limit(args.limit)

        movies = query.all()
        for movie in movies:
            credits = fetch_tmdb_credits(client, api_key, movie.tmdb_id or 0)
            if not credits:
                missing += 1
                continue

            movie_roles: List[Role] = []

            cast = credits.get("cast") or []
            for member in cast[:12]:
                name = member.get("name") or ""
                tmdb_pid = member.get("id")
                imdb_pid = member.get("imdb_id")
                character = member.get("character")
                order_idx = member.get("order")
                if not name:
                    continue
                person_id = upsert_person(db, name, tmdb_pid, imdb_pid)
                movie_roles.append(
                    Role(
                        movie_id=movie.id,
                        person_id=person_id,
                        role_type=RoleType.ACTOR,
                        character_name=character,
                        billing_order=order_idx,
                    )
                )

            crew = credits.get("crew") or []
            for member in crew:
                name = member.get("name") or ""
                tmdb_pid = member.get("id")
                imdb_pid = member.get("imdb_id")
                job = (member.get("job") or "").lower()
                role_type = None
                if "director" in job:
                    role_type = RoleType.DIRECTOR
                elif "writer" in job or "screenplay" in job:
                    role_type = RoleType.WRITER
                if not role_type:
                    continue
                if not name:
                    continue
                person_id = upsert_person(db, name, tmdb_pid, imdb_pid)
                movie_roles.append(
                    Role(
                        movie_id=movie.id,
                        person_id=person_id,
                        role_type=role_type,
                        character_name=None,
                        billing_order=None,
                    )
                )

            if not movie_roles:
                skipped += 1
                continue

            if args.apply:
                db.query(Role).filter(Role.movie_id == movie.id).delete()
                db.add_all(movie_roles)
                db.commit()
            updated += 1

    print(f"updated: {updated}, skipped: {skipped}, missing: {missing}, errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_provider_cli(main))
