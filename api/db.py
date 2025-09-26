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
            "where_to_watch": "ALTER TABLE movies ADD COLUMN where_to_watch TEXT",
            "languages": "ALTER TABLE movies ADD COLUMN languages TEXT",
            "countries": "ALTER TABLE movies ADD COLUMN countries TEXT",
            "collection": "ALTER TABLE movies ADD COLUMN collection TEXT",
        }

        for column_name, ddl in migrations.items():
            if column_name not in columns:
                connection.execute(text(ddl))

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


_ensure_sqlite_movie_columns()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
