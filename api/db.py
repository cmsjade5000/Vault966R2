from collections.abc import Generator

import logging
import os
import sqlite3

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from api.config import settings

DEFAULT_SQLITE = "sqlite:///./vault.db"
DB_URL = settings.database_url or DEFAULT_SQLITE

# SQLite serves the local always-on deployment, where concurrent browser requests can
# otherwise fail immediately while a write is in progress.
connect_args = {"check_same_thread": False, "timeout": 15.0} if DB_URL.startswith("sqlite") else {}

engine = create_engine(
    DB_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


logger = logging.getLogger(__name__)

SQLITE_REQUIRED_MOVIE_COLUMNS = {
    "id",
    "title",
    "vault_id",
    "imdb_id",
    "tmdb_id",
}
SQLITE_REQUIRED_UNIQUE_INDEXES = {
    "ix_movies_imdb_id",
    "ix_movies_tmdb_id",
    "ix_movies_vault_id",
}
LEGACY_RETIRED_VAULT_IDS = (
    "V0087",
    "V0135",
    "V0288",
    "V0309",
    "V0539",
    "V0584",
    "V0631",
    "V0637",
    "V0643",
    "V0695",
    "V0942",
)


class Base(DeclarativeBase):
    pass


def _configure_sqlite_connection(
    dbapi_connection: sqlite3.Connection, _connection_record: object
) -> None:
    """Apply reliability and concurrency settings to every SQLite connection."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


if DB_URL.startswith("sqlite"):
    event.listen(engine, "connect", _configure_sqlite_connection)


def should_bootstrap_sqlite_schema() -> bool:
    if not DB_URL.startswith("sqlite"):
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return True


def _duplicate_values(connection, column_name: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            text(
                f"""
                SELECT {column_name} FROM movies
                WHERE {column_name} IS NOT NULL
                GROUP BY {column_name}
                HAVING COUNT(*) > 1
                """
            )
        )
    ]


def _create_movie_identity_indexes(connection) -> None:
    try:
        for index_name, column_name in (
            ("ix_movies_imdb_id", "imdb_id"),
            ("ix_movies_tmdb_id", "tmdb_id"),
            ("ix_movies_vault_id", "vault_id"),
        ):
            connection.execute(
                text(
                    f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
                    ON movies ({column_name})
                    """
                )
            )
    except IntegrityError as exc:
        if connection.in_transaction():
            connection.rollback()

        with engine.connect() as diagnostic_conn:
            duplicate_summary = {
                column_name: _duplicate_values(diagnostic_conn, column_name)
                for column_name in ("tmdb_id", "imdb_id", "vault_id")
            }

        guidance_message = (
            "Creating unique indexes on movies identity fields failed due to duplicate values. "
            "tmdb_id duplicates: {tmdb}; imdb_id duplicates: {imdb}; vault_id duplicates: {vault}."
        ).format(
            tmdb=", ".join(duplicate_summary["tmdb_id"]) or "none",
            imdb=", ".join(duplicate_summary["imdb_id"]) or "none",
            vault=", ".join(duplicate_summary["vault_id"]) or "none",
        )

        logger.error(guidance_message)
        raise IntegrityError(guidance_message, exc.params, exc.orig) from exc


def _verify_sqlite_schema_invariants() -> None:
    if not DB_URL.startswith("sqlite"):
        return
    with engine.connect() as connection:
        table_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='movies'")
        ).first()
        if not table_exists:
            return

        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(movies)"))}
        missing_columns = sorted(SQLITE_REQUIRED_MOVIE_COLUMNS - columns)
        index_rows = list(connection.execute(text("PRAGMA index_list(movies)")))
        unique_indexes = {row[1] for row in index_rows if bool(row[2])}
        missing_indexes = sorted(SQLITE_REQUIRED_UNIQUE_INDEXES - unique_indexes)

    if missing_columns or missing_indexes:
        raise RuntimeError(
            "SQLite schema drift detected. "
            f"Missing movie columns: {missing_columns or 'none'}; "
            f"missing unique indexes: {missing_indexes or 'none'}. "
            "Run the migration/bootstrap maintenance workflow before starting Vault 966."
        )


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
            "vault_id": "ALTER TABLE movies ADD COLUMN vault_id TEXT",
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
            "certificate": "ALTER TABLE movies ADD COLUMN certificate TEXT",
            "keywords": "ALTER TABLE movies ADD COLUMN keywords JSON",
            "last_tmdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_tmdb_fetch_at TIMESTAMP",
            "last_omdb_fetch_at": "ALTER TABLE movies ADD COLUMN last_omdb_fetch_at TIMESTAMP",
            "tmdb_etag": "ALTER TABLE movies ADD COLUMN tmdb_etag TEXT",
            "tmdb_payload_sha": "ALTER TABLE movies ADD COLUMN tmdb_payload_sha TEXT",
            "omdb_payload_sha": "ALTER TABLE movies ADD COLUMN omdb_payload_sha TEXT",
            "trailer_site": "ALTER TABLE movies ADD COLUMN trailer_site TEXT",
            "trailer_key": "ALTER TABLE movies ADD COLUMN trailer_key TEXT",
            "trailer_name": "ALTER TABLE movies ADD COLUMN trailer_name TEXT",
            "trailer_url": "ALTER TABLE movies ADD COLUMN trailer_url TEXT",
            "trailer_checked_at": "ALTER TABLE movies ADD COLUMN trailer_checked_at TIMESTAMP",
        }

        for column_name, ddl in migrations.items():
            if column_name not in columns:
                connection.execute(text(ddl))

        _create_movie_identity_indexes(connection)

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
                        reported_by_profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                    """
                )
            )
        else:
            flag_columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(movie_flags)"))
            }
            if "reported_by_profile_id" not in flag_columns:
                connection.execute(
                    text(
                        """
                        ALTER TABLE movie_flags
                        ADD COLUMN reported_by_profile_id INTEGER
                        REFERENCES profiles(id) ON DELETE SET NULL
                        """
                    )
                )

        review_checks_exists = connection.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='movie_review_checks'"
            )
        ).first()
        if not review_checks_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_review_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                        issue_type TEXT NOT NULL,
                        issue_fingerprint TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        checked_by_profile_id INTEGER REFERENCES profiles(id)
                            ON DELETE SET NULL,
                        checked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(movie_id, issue_type, issue_fingerprint)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_review_checks_movie_id
                    ON movie_review_checks (movie_id)
                    """
                )
            )

        identity_repairs_exists = connection.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='movie_identity_repairs'"
            )
        ).first()
        if not identity_repairs_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE movie_identity_repairs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                        applied_by_profile_id INTEGER REFERENCES profiles(id)
                            ON DELETE SET NULL,
                        source TEXT NOT NULL,
                        search_title TEXT NOT NULL,
                        standardized_title TEXT NOT NULL,
                        selected_title TEXT NOT NULL,
                        selected_year INTEGER,
                        selected_imdb_id TEXT,
                        selected_tmdb_id INTEGER,
                        before_values JSON,
                        after_values JSON,
                        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_identity_repairs_movie_id
                    ON movie_identity_repairs (movie_id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_movie_identity_repairs_applied_at
                    ON movie_identity_repairs (applied_at)
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

        maintenance_jobs_exists = connection.execute(
            text("SELECT name FROM sqlite_master " "WHERE type='table' AND name='maintenance_jobs'")
        ).first()
        if not maintenance_jobs_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE maintenance_jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        started_by_profile_id INTEGER REFERENCES profiles(id)
                            ON DELETE SET NULL,
                        started_at TIMESTAMP NOT NULL,
                        finished_at TIMESTAMP,
                        last_error TEXT,
                        steps JSON,
                        reports JSON,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_maintenance_jobs_run_id
                    ON maintenance_jobs (run_id)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_maintenance_jobs_task_started
                    ON maintenance_jobs (task_id, started_at)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_maintenance_jobs_state
                    ON maintenance_jobs (state)
                    """
                )
            )

        retired_vault_ids_exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='retired_vault_ids'")
        ).first()
        if not retired_vault_ids_exists:
            connection.execute(
                text(
                    """
                    CREATE TABLE retired_vault_ids (
                        vault_id TEXT PRIMARY KEY,
                        retired_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        source TEXT NOT NULL,
                        reason TEXT,
                        deleted_movie_id INTEGER,
                        deleted_movie_title TEXT
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_retired_vault_ids_retired_at
                    ON retired_vault_ids (retired_at)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_retired_vault_ids_source
                    ON retired_vault_ids (source)
                    """
                )
            )

        for vault_id in LEGACY_RETIRED_VAULT_IDS:
            connection.execute(
                text(
                    """
                    INSERT OR IGNORE INTO retired_vault_ids
                        (vault_id, source, reason)
                    VALUES
                        (:vault_id, 'legacy_gap', 'Known legacy Vault ID gap reserved to prevent reuse.')
                    """
                ),
                {"vault_id": vault_id},
            )


def bootstrap_sqlite_schema() -> None:
    """Best-effort bootstrap for SQLite local dev and legacy `vault.db` dumps."""

    if not should_bootstrap_sqlite_schema():
        return

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_movie_columns()
    _verify_sqlite_schema_invariants()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
