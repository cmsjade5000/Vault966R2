import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

import api.db as db


def test_duplicate_movie_ids_surface_in_error_message(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "DB_URL", "sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE movies (
                    id INTEGER PRIMARY KEY,
                    vault_id TEXT,
                    imdb_id TEXT,
                    tmdb_id INTEGER
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO movies (id, vault_id, imdb_id, tmdb_id) "
                "VALUES (1, 'V0001', 'tt0001', 100)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO movies (id, vault_id, imdb_id, tmdb_id) "
                "VALUES (2, 'V0002', 'tt0001', 101)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO movies (id, vault_id, imdb_id, tmdb_id) "
                "VALUES (3, 'V0001', 'tt0002', 100)"
            )
        )

    with pytest.raises(IntegrityError) as excinfo:
        db._ensure_sqlite_movie_columns()

    message = str(excinfo.value)
    assert "tmdb_id duplicates: 100" in message
    assert "imdb_id duplicates: tt0001" in message
    assert "vault_id duplicates: V0001" in message


def test_sqlite_schema_invariant_check_reports_missing_identity_index(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "DB_URL", "sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE movies (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    vault_id TEXT,
                    imdb_id TEXT,
                    tmdb_id INTEGER
                )
                """
            )
        )
        connection.execute(text("CREATE UNIQUE INDEX ix_movies_imdb_id ON movies (imdb_id)"))
        connection.execute(text("CREATE UNIQUE INDEX ix_movies_tmdb_id ON movies (tmdb_id)"))

    with pytest.raises(RuntimeError) as excinfo:
        db._verify_sqlite_schema_invariants()

    assert "SQLite schema drift detected" in str(excinfo.value)
    assert "ix_movies_vault_id" in str(excinfo.value)


def test_sqlite_bootstrap_creates_vault_id_unique_index(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "DB_URL", "sqlite://")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE movies (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    imdb_id TEXT,
                    tmdb_id INTEGER
                )
                """
            )
        )

    db._ensure_sqlite_movie_columns()
    db._verify_sqlite_schema_invariants()

    with engine.connect() as connection:
        index_rows = list(connection.execute(text("PRAGMA index_list(movies)")))

    unique_indexes = {row[1] for row in index_rows if bool(row[2])}
    assert "ix_movies_vault_id" in unique_indexes
