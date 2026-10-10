"""Exercise the additive migration on a synthetic previous-release schema."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_personal_migration_preserves_existing_rows_and_blocks_unsafe_downgrade(
    tmp_path, monkeypatch
):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/202610060001_personal_sign_in.py"
    spec = importlib.util.spec_from_file_location("personal_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE profiles (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE app_setup (id INTEGER PRIMARY KEY, completed BOOLEAN NOT NULL DEFAULT false, completed_at TIMESTAMP, owner_profile_id INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE movie_preferences (id INTEGER PRIMARY KEY, profile_id INTEGER, movie_id INTEGER, watchlist BOOLEAN)"
            )
        )
        connection.execute(
            text("INSERT INTO profiles(id,name,role) VALUES (1,'Synthetic original','admin')")
        )
        connection.execute(
            text("INSERT INTO app_setup(id,completed,owner_profile_id) VALUES (1,true,1)")
        )
        connection.execute(text("INSERT INTO movie_preferences VALUES (1,1,1,true)"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        assert connection.execute(
            text("SELECT name,role,session_revision,archived_at FROM profiles")
        ).one() == ("Synthetic original", "admin", 0, None)
        assert connection.execute(
            text("SELECT completed,personal_sign_in_only,local_setup_only FROM app_setup")
        ).one() == (1, 0, 0)
        assert connection.execute(text("SELECT COUNT(*) FROM movie_preferences")).scalar() == 1
        connection.execute(
            text(
                "INSERT INTO profile_archive_batches(id,previous_setup_completed,previous_personal_sign_in_only,previous_local_setup_only,created_at) VALUES ('synthetic',true,false,false,CURRENT_TIMESTAMP)"
            )
        )
        with pytest.raises(RuntimeError, match="unsafe"):
            migration.downgrade()
        assert "session_revision" in {
            col["name"] for col in inspect(connection).get_columns("profiles")
        }
    engine.dispose()
