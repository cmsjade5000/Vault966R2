from collections.abc import Generator

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import settings

DEFAULT_SQLITE = "sqlite:///./vault.db"
DB_URL = settings.database_url or DEFAULT_SQLITE

# Check if SQLite; need check_same_thread False for SQLite
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def should_bootstrap_sqlite_schema() -> bool:
    if not DB_URL.startswith("sqlite"):
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _ensure_sqlite_movie_columns() -> None:
    if not DB_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        table_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movies'")
        ).first()
        if not table_exists:
            return

        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(movies)"))}

        migrations = {
            "imdb_rating": "ALTER TABLE movies ADD COLUMN imdb_rating FLOAT",
            "imdb_votes": "ALTER TABLE movies ADD COLUMN imdb_votes INTEGER",
            "rt_score": "ALTER TABLE movies ADD COLUMN rt_score INTEGER",
            "metascore": "ALTER TABLE movies ADD COLUMN metascore INTEGER",
            "tomato_meter": "ALTER TABLE movies ADD COLUMN tomato_meter INTEGER",
            "tomato_audience": "ALTER TABLE movies ADD COLUMN tomato_audience INTEGER",
            "where_to_watch": "ALTER TABLE movies ADD COLUMN where_to_watch TEXT",
            "languages": "ALTER TABLE movies ADD COLUMN languages TEXT",
            "countries": "ALTER TABLE movies ADD COLUMN countries TEXT",
            "collection": "ALTER TABLE movies ADD COLUMN collection TEXT",
            "awards": "ALTER TABLE movies ADD COLUMN awards TEXT",
            "last_tmdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_tmdb_fetch_at TIMESTAMP",
            "last_omdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_omdb_fetch_at TIMESTAMP",
            "tmdb_etag": "ALTER TABLE movies ADD COLUMN tmdb_etag TEXT",
            "tmdb_payload_sha": "ALTER TABLE movies ADD COLUMN tmdb_payload_sha TEXT",
            "omdb_payload_sha": "ALTER TABLE movies ADD COLUMN omdb_payload_sha TEXT",
        }

        for column_name, ddl in migrations.items():
            if column_name not in columns:
                connection.execute(text(ddl))

        try:
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_movies_imdb_id ON movies (imdb_id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_movies_tmdb_id ON movies (tmdb_id)
                    """
                )
            )
        except IntegrityError as exc:
            if connection.in_transaction():
                connection.rollback()

            with engine.connect() as diagnostic_conn:
                tmdb_duplicates = [
                    row[0]
                    for row in diagnostic_conn.execute(
                        text(
                            """
                            SELECT tmdb_id FROM movies
                            WHERE tmdb_id IS NOT NULL
                            GROUP BY tmdb_id
                            HAVING COUNT(*) > 1
                            """
                        )
                    )
                ]
                imdb_duplicates = [
                    row[0]
                    for row in diagnostic_conn.execute(
                        text(
                            """
                            SELECT imdb_id FROM movies
                            WHERE imdb_id IS NOT NULL
                            GROUP BY imdb_id
                            HAVING COUNT(*) > 1
                            """
                        )
                    )
                ]

            guidance_message = (
                "Creating unique indexes on movies.imdb_id/movies.tmdb_id failed due to duplicate "
                "values. tmdb_id duplicates: {tmdb}; imdb_id duplicates: {imdb}."
            ).format(
                tmdb=", ".join(map(str, tmdb_duplicates)) or "none",
                imdb=", ".join(map(str, imdb_duplicates)) or "none",
            )

            logger.error(guidance_message)
            raise IntegrityError(guidance_message, exc.params, exc.orig) from exc

        # Minimal boot-strap for legacy SQLite dumps; keep in sync with models.
        flags_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movie_flags'")
        ).first()
        if not flags_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_flags (
                        movie_id INTEGER PRIMARY KEY REFERENCES movies(id) ON DELETE CASCADE,
                        reason TEXT,
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """
                )
            )

        movie_cast_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movie_cast'")
        ).first()
        if not movie_cast_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_cast (
                        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                        character TEXT,
                        order_index INTEGER,
                        PRIMARY KEY (movie_id, person_id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_cast_movie_id
                    ON movie_cast (movie_id)
                    """
                )
            )

        movie_crew_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movie_crew'")
        ).first()
        if not movie_crew_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_crew (
                        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
                        department TEXT,
                        job TEXT,
                        PRIMARY KEY (movie_id, person_id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_crew_movie_id
                    ON movie_crew (movie_id)
                    """
                )
            )

        ai_cache_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_cache'")
        ).first()
        if not ai_cache_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE ai_cache (
                        cache_key TEXT PRIMARY KEY,
                        value JSON NOT NULL,
                        expires_at TIMESTAMP NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_ai_cache_expires_at
                    ON ai_cache (expires_at)
                    """
                )
            )

        movie_documents_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movie_documents'")
        ).first()
        if not movie_documents_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_documents (
                        movie_id INTEGER PRIMARY KEY REFERENCES movies(id) ON DELETE CASCADE,
                        doc_version INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding JSON NOT NULL,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_documents_movie_id
                    ON movie_documents (movie_id)
                    """
                )
            )
        provenance_exists = connection.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='movie_ingest_provenance'"
            )
        ).first()
        if not provenance_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_ingest_provenance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                        provider TEXT NOT NULL,
                        provider_id TEXT,
                        ingested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        payload_sha TEXT,
                        etag TEXT,
                        source_url TEXT,
                        notes TEXT,
                        UNIQUE(movie_id, provider)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_ingest_provenance_movie_id
                    ON movie_ingest_provenance (movie_id)
                    """
                )
            )


def bootstrap_sqlite_schema() -> None:
    """Best-effort bootstrap for SQLite local dev and legacy `vault.db` dumps."""

    if not should_bootstrap_sqlite_schema():
        return

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_movie_columns()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
