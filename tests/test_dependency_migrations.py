"""Replay real SQLite migrations on generated data, never on the user's database."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]


def test_sqlite_migration_upgrade_preserves_data_and_constraints(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.sqlite'}"
    env = {**os.environ, "DATABASE_URL": url}

    def migrate(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    migrate("upgrade", "202601250002")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO movies (id, title) VALUES (900001, 'Migration probe')"))
        before = {c["name"] for c in inspect(engine).get_check_constraints("movies")}
        migrate("upgrade", "head")
        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT title FROM movies WHERE id=900001")).scalar_one()
                == "Migration probe"
            )
            assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
            assert conn.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        inspector = inspect(engine)
        assert before <= {c["name"] for c in inspector.get_check_constraints("movies")}
        assert {"certificate", "keywords", "vault_id"} <= {
            c["name"] for c in inspector.get_columns("movies")
        }
        indexes = {i["name"] for i in inspector.get_indexes("movies")}
        assert "ix_movies_tmdb_id" in indexes
        assert any(
            c["column_names"] == ["imdb_id"] for c in inspector.get_unique_constraints("movies")
        )
        migrate("downgrade", "202607020001")
        migrate("upgrade", "head")
    finally:
        engine.dispose()
