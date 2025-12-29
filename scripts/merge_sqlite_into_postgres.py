#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

SQLITE_URL = "sqlite:///./vault.db"
DEFAULT_PG_URL = "postgresql+psycopg://vault_user:vault_pass@localhost:5432/vault966"
JSON_COLUMNS = {"where_to_watch", "languages", "countries"}


def _normalize_json(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
        return value
    return value


def _normalize_value(column: str, value: object) -> object:
    if column in JSON_COLUMNS:
        return _normalize_json(value)
    return value


def _load_rows(conn, table: Table, *, where_clause=None) -> list[dict[str, object]]:
    stmt = select(table)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    return [dict(row) for row in conn.execute(stmt).mappings()]


def _load_mapping(conn, table: Table, keys: Iterable[str]) -> list[dict[str, object]]:
    columns = [table.c[key] for key in keys]
    return [dict(row) for row in conn.execute(select(*columns)).mappings()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge movies (and related metadata) from SQLite into Postgres.",
    )
    parser.add_argument(
        "--sqlite-url",
        default=SQLITE_URL,
        help="SQLite DB URL (default: sqlite:///./vault.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL") or DEFAULT_PG_URL,
        help="Postgres DB URL (default: env DATABASE_URL or local vault966)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (otherwise dry-run).",
    )
    args = parser.parse_args()

    sqlite_engine = create_engine(args.sqlite_url)
    pg_engine = create_engine(args.postgres_url)

    sqlite_meta = MetaData()
    pg_meta = MetaData()
    movies_sqlite = Table("movies", sqlite_meta, autoload_with=sqlite_engine)
    movies_pg = Table("movies", pg_meta, autoload_with=pg_engine)
    genres_sqlite = Table("genres", sqlite_meta, autoload_with=sqlite_engine)
    genres_pg = Table("genres", pg_meta, autoload_with=pg_engine)
    moods_sqlite = Table("moods", sqlite_meta, autoload_with=sqlite_engine)
    moods_pg = Table("moods", pg_meta, autoload_with=pg_engine)
    movie_genres_sqlite = Table("movie_genres", sqlite_meta, autoload_with=sqlite_engine)
    movie_genres_pg = Table("movie_genres", pg_meta, autoload_with=pg_engine)
    movie_moods_sqlite = Table("movie_moods", sqlite_meta, autoload_with=sqlite_engine)
    movie_moods_pg = Table("movie_moods", pg_meta, autoload_with=pg_engine)
    people_sqlite = Table("people", sqlite_meta, autoload_with=sqlite_engine)
    people_pg = Table("people", pg_meta, autoload_with=pg_engine)
    roles_sqlite = Table("roles", sqlite_meta, autoload_with=sqlite_engine)
    roles_pg = Table("roles", pg_meta, autoload_with=pg_engine)
    ingest_sqlite = Table("movie_ingest_provenance", sqlite_meta, autoload_with=sqlite_engine)
    ingest_pg = Table("movie_ingest_provenance", pg_meta, autoload_with=pg_engine)

    with sqlite_engine.connect() as sqlite_conn, pg_engine.connect() as pg_conn:
        sqlite_movies = _load_rows(sqlite_conn, movies_sqlite)
        pg_movies = _load_rows(pg_conn, movies_pg)

    sqlite_by_imdb = {row["imdb_id"]: row for row in sqlite_movies if row.get("imdb_id")}
    pg_by_imdb = {row["imdb_id"]: row for row in pg_movies if row.get("imdb_id")}

    sqlite_imdb_ids = set(sqlite_by_imdb.keys())
    pg_imdb_ids = set(pg_by_imdb.keys())
    missing_imdb_ids = sorted(sqlite_imdb_ids - pg_imdb_ids)
    overlap_imdb_ids = sorted(sqlite_imdb_ids & pg_imdb_ids)

    movie_columns = [
        column.name
        for column in movies_pg.columns
        if column.name in movies_sqlite.c and column.name != "id"
    ]

    update_candidates = 0
    for imdb_id in overlap_imdb_ids:
        source = sqlite_by_imdb[imdb_id]
        target = pg_by_imdb[imdb_id]
        for column in movie_columns:
            if column == "imdb_id":
                continue
            if target.get(column) is None and source.get(column) is not None:
                update_candidates += 1
                break

    print(f"SQLite movies: {len(sqlite_movies)}")
    print(f"Postgres movies: {len(pg_movies)}")
    print(f"Missing in Postgres: {len(missing_imdb_ids)}")
    print(f"Existing movies with fillable fields: {update_candidates}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to merge.")
        return 0

    with sqlite_engine.connect() as sqlite_conn, pg_engine.begin() as pg_conn:
        rows_to_insert: list[dict[str, object]] = []
        for imdb_id in missing_imdb_ids:
            source = sqlite_by_imdb[imdb_id]
            payload = {
                column: _normalize_value(column, source.get(column)) for column in movie_columns
            }
            rows_to_insert.append(payload)

        if rows_to_insert:
            pg_conn.execute(
                pg_insert(movies_pg)
                .values(rows_to_insert)
                .on_conflict_do_nothing(index_elements=["imdb_id"])
            )

        for imdb_id in overlap_imdb_ids:
            source = sqlite_by_imdb[imdb_id]
            target = pg_by_imdb[imdb_id]
            update_payload = {}
            for column in movie_columns:
                if column == "imdb_id":
                    continue
                if target.get(column) is None and source.get(column) is not None:
                    update_payload[column] = _normalize_value(column, source.get(column))
            if update_payload:
                pg_conn.execute(
                    movies_pg.update()
                    .where(movies_pg.c.id == target["id"])
                    .values(**update_payload)
                )

        if not missing_imdb_ids:
            return 0

        missing_sqlite_ids = [
            row["id"] for row in sqlite_movies if row.get("imdb_id") in missing_imdb_ids
        ]
        pg_movie_rows = _load_mapping(
            pg_conn,
            movies_pg,
            ("id", "imdb_id"),
        )
        pg_movie_by_imdb = {row["imdb_id"]: row["id"] for row in pg_movie_rows if row["imdb_id"]}
        movie_id_map = {
            row["id"]: pg_movie_by_imdb.get(row["imdb_id"])
            for row in sqlite_movies
            if row.get("imdb_id") in missing_imdb_ids
        }

        sqlite_genres = _load_mapping(sqlite_conn, genres_sqlite, ("id", "name"))
        sqlite_genre_by_id = {row["id"]: row["name"] for row in sqlite_genres}
        sqlite_movie_genres = _load_rows(
            sqlite_conn,
            movie_genres_sqlite,
            where_clause=movie_genres_sqlite.c.movie_id.in_(missing_sqlite_ids),
        )
        genre_names = {
            sqlite_genre_by_id.get(row["genre_id"])
            for row in sqlite_movie_genres
            if sqlite_genre_by_id.get(row["genre_id"])
        }
        if genre_names:
            pg_conn.execute(
                pg_insert(genres_pg)
                .values([{"name": name} for name in sorted(genre_names)])
                .on_conflict_do_nothing(index_elements=["name"])
            )
        pg_genres = _load_mapping(pg_conn, genres_pg, ("id", "name"))
        pg_genre_by_name = {row["name"]: row["id"] for row in pg_genres}
        movie_genre_rows = []
        for row in sqlite_movie_genres:
            movie_id = movie_id_map.get(row["movie_id"])
            genre_name = sqlite_genre_by_id.get(row["genre_id"])
            genre_id = pg_genre_by_name.get(genre_name) if genre_name else None
            if movie_id and genre_id:
                movie_genre_rows.append({"movie_id": movie_id, "genre_id": genre_id})
        if movie_genre_rows:
            pg_conn.execute(
                pg_insert(movie_genres_pg)
                .values(movie_genre_rows)
                .on_conflict_do_nothing(index_elements=["movie_id", "genre_id"])
            )

        sqlite_moods = _load_rows(sqlite_conn, moods_sqlite)
        sqlite_mood_by_id = {row["id"]: row for row in sqlite_moods}
        sqlite_movie_moods = _load_rows(
            sqlite_conn,
            movie_moods_sqlite,
            where_clause=movie_moods_sqlite.c.movie_id.in_(missing_sqlite_ids),
        )
        mood_rows = []
        for row in sqlite_movie_moods:
            mood = sqlite_mood_by_id.get(row["mood_id"])
            if not mood:
                continue
            mood_rows.append(
                {
                    "name": mood.get("name"),
                    "description": mood.get("description"),
                    "emoji": mood.get("emoji"),
                }
            )
        if mood_rows:
            pg_conn.execute(
                pg_insert(moods_pg)
                .values(mood_rows)
                .on_conflict_do_nothing(index_elements=["name"])
            )
        pg_moods = _load_mapping(pg_conn, moods_pg, ("id", "name"))
        pg_mood_by_name = {row["name"]: row["id"] for row in pg_moods}
        movie_mood_rows = []
        for row in sqlite_movie_moods:
            movie_id = movie_id_map.get(row["movie_id"])
            mood = sqlite_mood_by_id.get(row["mood_id"])
            mood_id = pg_mood_by_name.get(mood.get("name")) if mood else None
            if movie_id and mood_id:
                movie_mood_rows.append({"movie_id": movie_id, "mood_id": mood_id})
        if movie_mood_rows:
            pg_conn.execute(
                pg_insert(movie_moods_pg)
                .values(movie_mood_rows)
                .on_conflict_do_nothing(index_elements=["movie_id", "mood_id"])
            )

        sqlite_roles = _load_rows(
            sqlite_conn,
            roles_sqlite,
            where_clause=roles_sqlite.c.movie_id.in_(missing_sqlite_ids),
        )
        if sqlite_roles:
            person_ids = {row["person_id"] for row in sqlite_roles if row.get("person_id")}
            sqlite_people = _load_rows(
                sqlite_conn,
                people_sqlite,
                where_clause=people_sqlite.c.id.in_(person_ids),
            )
            people_rows = []
            for person in sqlite_people:
                people_rows.append(
                    {
                        "name": person.get("name"),
                        "tmdb_id": person.get("tmdb_id"),
                        "imdb_id": person.get("imdb_id"),
                    }
                )
            if people_rows:
                pg_conn.execute(
                    pg_insert(people_pg)
                    .values(people_rows)
                    .on_conflict_do_nothing(index_elements=["name", "tmdb_id"])
                )

            pg_people = _load_rows(pg_conn, people_pg)
            by_tmdb = {row["tmdb_id"]: row["id"] for row in pg_people if row.get("tmdb_id")}
            by_imdb = {row["imdb_id"]: row["id"] for row in pg_people if row.get("imdb_id")}
            by_name = {row["name"]: row["id"] for row in pg_people if row.get("name")}

            person_id_map = {}
            for person in sqlite_people:
                pg_id = None
                tmdb_id = person.get("tmdb_id")
                imdb_id = person.get("imdb_id")
                name = person.get("name")
                if tmdb_id in by_tmdb:
                    pg_id = by_tmdb[tmdb_id]
                elif imdb_id in by_imdb:
                    pg_id = by_imdb[imdb_id]
                elif name in by_name:
                    pg_id = by_name[name]
                if pg_id:
                    person_id_map[person["id"]] = pg_id

            role_rows = []
            for role in sqlite_roles:
                movie_id = movie_id_map.get(role["movie_id"])
                person_id = person_id_map.get(role["person_id"])
                if not movie_id or not person_id:
                    continue
                role_rows.append(
                    {
                        "movie_id": movie_id,
                        "person_id": person_id,
                        "role_type": role.get("role_type"),
                        "character_name": role.get("character_name"),
                        "billing_order": role.get("billing_order"),
                    }
                )
            if role_rows:
                pg_conn.execute(pg_insert(roles_pg).values(role_rows))

        sqlite_ingest = _load_rows(
            sqlite_conn,
            ingest_sqlite,
            where_clause=ingest_sqlite.c.movie_id.in_(missing_sqlite_ids),
        )
        ingest_rows = []
        for row in sqlite_ingest:
            movie_id = movie_id_map.get(row["movie_id"])
            if not movie_id:
                continue
            payload = {
                "movie_id": movie_id,
                "provider": row.get("provider"),
                "provider_id": row.get("provider_id"),
                "ingested_at": row.get("ingested_at"),
                "payload_sha": row.get("payload_sha"),
                "etag": row.get("etag"),
                "source_url": row.get("source_url"),
                "notes": row.get("notes"),
            }
            ingest_rows.append(payload)
        if ingest_rows:
            pg_conn.execute(
                pg_insert(ingest_pg)
                .values(ingest_rows)
                .on_conflict_do_nothing(index_elements=["movie_id", "provider"])
            )

    print("Merge complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
