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
                    imdb_id TEXT,
                    tmdb_id INTEGER
                )
                """
            )
        )
        connection.execute(
            text("INSERT INTO movies (id, imdb_id, tmdb_id) VALUES (1, 'tt0001', 100)")
        )
        connection.execute(
            text("INSERT INTO movies (id, imdb_id, tmdb_id) VALUES (2, 'tt0001', 101)")
        )
        connection.execute(
            text("INSERT INTO movies (id, imdb_id, tmdb_id) VALUES (3, 'tt0002', 100)")
        )

    with pytest.raises(IntegrityError) as excinfo:
        db._ensure_sqlite_movie_columns()

    message = str(excinfo.value)
    assert "tmdb_id duplicates: 100" in message
    assert "imdb_id duplicates: tt0001" in message
