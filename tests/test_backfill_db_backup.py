import pathlib
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from scripts import (
    backfill_backdrops,
    backfill_clear_external_matches,
    backfill_posters,
    backfill_ratings_db,
)
from scripts.backfill_db_backup import (
    BackfillBackupError,
    active_sqlite_database_path,
    backup_active_sqlite_database,
)


def test_active_sqlite_database_path_resolves_relative_database(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite:///active.db")

    assert active_sqlite_database_path(engine) == tmp_path / "active.db"


def test_backup_active_sqlite_database_uses_engine_database(
    tmp_path: pathlib.Path,
) -> None:
    database = tmp_path / "active.db"
    engine = create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)"))
        connection.execute(text("INSERT INTO sample (name) VALUES ('backed-up')"))

    result = backup_active_sqlite_database("test backfill", engine=engine)

    backup = pathlib.Path(result.backup)
    assert pathlib.Path(result.source) == database
    assert backup.parent == database.parent
    assert backup.exists()
    assert backup != database
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT name FROM sample").fetchone() == ("backed-up",)


def test_backup_active_sqlite_database_refuses_memory_database() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    with pytest.raises(BackfillBackupError, match="not a file-backed database"):
        backup_active_sqlite_database("test backfill", engine=engine)


def test_external_match_apply_aborts_when_backup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_backup(label: str, **_kwargs):
        calls.append(label)
        raise BackfillBackupError("backup failed")

    monkeypatch.setattr(
        backfill_clear_external_matches,
        "parse_args",
        lambda: SimpleNamespace(dry_run=False, limit=0, flags_only=False, report="report.csv"),
    )
    monkeypatch.setattr(backfill_clear_external_matches.settings, "tmdb_api_key", "tmdb-key")
    monkeypatch.setattr(backfill_clear_external_matches.settings, "omdb_api_key", "omdb-key")
    monkeypatch.setattr(
        backfill_clear_external_matches,
        "backup_active_sqlite_database",
        fail_backup,
    )

    with pytest.raises(BackfillBackupError, match="backup failed"):
        backfill_clear_external_matches.main()

    assert calls == ["external-match sweep"]


def test_poster_write_run_aborts_when_backup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_backup(label: str, **_kwargs):
        calls.append(label)
        raise BackfillBackupError("backup failed")

    monkeypatch.setattr(
        backfill_posters,
        "parse_args",
        lambda: SimpleNamespace(
            workers=1,
            tmdb_key=None,
            omdb_key=None,
            dry_run=False,
            report="report.csv",
            include_review=False,
            limit=0,
            sleep=0,
            min_confidence=0.72,
            update_tmdb_id=False,
        ),
    )
    monkeypatch.setattr(backfill_posters, "backup_active_sqlite_database", fail_backup)

    with pytest.raises(BackfillBackupError, match="backup failed"):
        backfill_posters.main()

    assert calls == ["poster backfill"]


def test_backdrop_apply_aborts_when_backup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_backup(label: str, **_kwargs):
        calls.append(label)
        raise BackfillBackupError("backup failed")

    monkeypatch.setattr(
        backfill_backdrops,
        "parse_args",
        lambda: SimpleNamespace(
            tmdb_key="tmdb-key",
            apply=True,
            dry_run=False,
            report="report.csv",
            limit=0,
            sleep=0,
            min_confidence=0.72,
            retries=0,
            backoff=0,
            update_tmdb_id=False,
        ),
    )
    monkeypatch.setattr(backfill_backdrops, "backup_active_sqlite_database", fail_backup)

    with pytest.raises(BackfillBackupError, match="backup failed"):
        backfill_backdrops.main()

    assert calls == ["backdrop backfill"]


def test_ratings_apply_aborts_when_backup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fail_backup(label: str, **_kwargs):
        calls.append(label)
        raise BackfillBackupError("backup failed")

    monkeypatch.setattr(
        backfill_ratings_db,
        "parse_args",
        lambda: SimpleNamespace(
            omdb_key="omdb-key",
            apply=True,
            report="report.csv",
            limit=0,
        ),
    )
    monkeypatch.setattr(backfill_ratings_db, "backup_active_sqlite_database", fail_backup)

    with pytest.raises(BackfillBackupError, match="backup failed"):
        backfill_ratings_db.main()

    assert calls == ["ratings backfill"]
