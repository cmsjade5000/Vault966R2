from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import settings

DEFAULT_SQLITE = "sqlite:///./vault.db"
DB_URL = settings.database_url or DEFAULT_SQLITE

# Check if SQLite; need check_same_thread False for SQLite
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


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
            "tagline": "ALTER TABLE movies ADD COLUMN tagline TEXT",
            "awards": "ALTER TABLE movies ADD COLUMN awards TEXT",
            "revenue": "ALTER TABLE movies ADD COLUMN revenue BIGINT",
            "budget": "ALTER TABLE movies ADD COLUMN budget BIGINT",
            "last_tmdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_tmdb_fetch_at TIMESTAMP",
            "last_omdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_omdb_fetch_at TIMESTAMP",
            "tmdb_etag": "ALTER TABLE movies ADD COLUMN tmdb_etag TEXT",
            "tmdb_payload_sha": "ALTER TABLE movies ADD COLUMN tmdb_payload_sha TEXT",
            "omdb_payload_sha": "ALTER TABLE movies ADD COLUMN omdb_payload_sha TEXT",
        }

        for column_name, ddl in migrations.items():
            if column_name not in columns:
                connection.execute(text(ddl))

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


_ensure_sqlite_movie_columns()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
