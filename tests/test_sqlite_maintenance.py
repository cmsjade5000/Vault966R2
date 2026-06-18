from __future__ import annotations

import json
import pathlib
import sqlite3
import stat
from datetime import datetime, timezone

import pytest

from scripts import sqlite_maintenance
from scripts.sqlite_maintenance import MaintenanceError, check_database, create_backup


def _create_database(path: pathlib.Path, value: str = "original") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO records (value) VALUES (?)", (value,))


def test_integrity_check_is_read_only(tmp_path: pathlib.Path) -> None:
    database = tmp_path / "vault.db"
    _create_database(database)
    original_bytes = database.read_bytes()
    original_stat = database.stat()

    result = check_database(database)

    assert result.healthy is True
    assert result.check == "integrity_check"
    assert result.messages == ["ok"]
    assert database.read_bytes() == original_bytes
    assert database.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert sorted(path.name for path in tmp_path.iterdir()) == ["vault.db"]


def test_integrity_check_reports_corruption(tmp_path: pathlib.Path) -> None:
    database = tmp_path / "vault.db"
    _create_database(database)
    database.write_bytes(database.read_bytes()[:100])

    result = check_database(database)

    assert result.healthy is False
    assert result.messages
    assert result.messages != ["ok"]


def test_online_backup_includes_committed_wal_data(tmp_path: pathlib.Path) -> None:
    database = tmp_path / "vault.db"
    backups = tmp_path / "backups"
    writer = sqlite3.connect(database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE records (value TEXT NOT NULL)")
        writer.execute("INSERT INTO records (value) VALUES ('from-wal')")
        writer.commit()

        result = create_backup(
            database,
            backups,
            now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )
    finally:
        writer.close()

    backup = pathlib.Path(result.backup)
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM records").fetchall() == [("from-wal",)]
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert not list(backups.glob("*.partial-*"))


def test_backup_rotation_keeps_newest_completed_files(tmp_path: pathlib.Path) -> None:
    database = tmp_path / "vault.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    _create_database(database)
    old_names = [
        "vault-20260612T120000.000000Z.db",
        "vault-20260613T120000.000000Z.db",
        "vault-20260614T120000.000000Z.db",
    ]
    for name in old_names:
        (backups / name).write_text("old", encoding="utf-8")

    result = create_backup(
        database,
        backups,
        keep=2,
        now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
    )

    assert sorted(path.name for path in backups.glob("vault-*.db")) == [
        "vault-20260614T120000.000000Z.db",
        "vault-20260615T120000.000000Z.db",
    ]
    assert [pathlib.Path(path).name for path in result.removed] == old_names[:2]


def test_failed_backup_validation_does_not_publish_or_rotate(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "vault.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    _create_database(database)
    old_backup = backups / "vault-20260614T120000.000000Z.db"
    old_backup.write_text("preserve", encoding="utf-8")
    real_check = sqlite_maintenance.check_database

    def fail_backup_check(path: pathlib.Path, **kwargs):
        result = real_check(path, **kwargs)
        if ".partial-" in path.name:
            return sqlite_maintenance.IntegrityResult(
                database=str(path),
                check="integrity_check",
                healthy=False,
                messages=["forced failure"],
            )
        return result

    monkeypatch.setattr(sqlite_maintenance, "check_database", fail_backup_check)

    with pytest.raises(MaintenanceError, match="failed integrity_check"):
        create_backup(
            database,
            backups,
            keep=1,
            now=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )

    assert old_backup.read_text(encoding="utf-8") == "preserve"
    assert sorted(path.name for path in backups.iterdir()) == [old_backup.name]


def test_check_cli_returns_machine_readable_status(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "vault.db"
    _create_database(database)

    exit_code = sqlite_maintenance.main(["check", "--database", str(database), "--quick"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["healthy"] is True
    assert payload["check"] == "quick_check"
