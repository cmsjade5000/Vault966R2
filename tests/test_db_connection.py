import sqlite3

import pytest

from api.db import _configure_sqlite_connection


def _pragma(connection: sqlite3.Connection, name: str):
    return connection.execute(f"PRAGMA {name}").fetchone()[0]


def test_configure_sqlite_connection_enforces_integrity_and_waits_for_writes(tmp_path):
    connection = sqlite3.connect(tmp_path / "vault.db")
    try:
        _configure_sqlite_connection(connection, object())

        assert _pragma(connection, "foreign_keys") == 1
        assert _pragma(connection, "busy_timeout") == 15_000
        assert _pragma(connection, "journal_mode") == "wal"
        assert _pragma(connection, "synchronous") == 1

        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO child (parent_id) VALUES (999)")
    finally:
        connection.close()
