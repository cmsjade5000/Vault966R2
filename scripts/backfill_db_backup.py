"""Backup helpers for write-capable backfill scripts."""

from __future__ import annotations

import pathlib
from datetime import datetime

from sqlalchemy.engine import Engine

from api.db import engine as default_engine
from scripts.sqlite_maintenance import BackupResult, MaintenanceError, create_backup


class BackfillBackupError(RuntimeError):
    """Raised when a backfill cannot safely back up the active database."""


def active_sqlite_database_path(engine: Engine = default_engine) -> pathlib.Path:
    """Return the SQLite database file used by the active SQLAlchemy engine."""
    url = engine.url
    if not url.drivername.startswith("sqlite"):
        raise BackfillBackupError(f"Active database is not SQLite: {url.drivername}")

    database = url.database
    if not database or database == ":memory:":
        raise BackfillBackupError("Active SQLite database is not a file-backed database")

    path = pathlib.Path(database).expanduser()
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    return path.resolve()


def backup_active_sqlite_database(
    label: str,
    *,
    engine: Engine = default_engine,
    now: datetime | None = None,
) -> BackupResult:
    """Create a validated online backup for the active SQLite database."""
    database = active_sqlite_database_path(engine)
    try:
        return create_backup(database, database.parent, keep=1000, now=now)
    except MaintenanceError as exc:
        raise BackfillBackupError(
            f"Could not back up active database before {label}: {exc}"
        ) from exc
