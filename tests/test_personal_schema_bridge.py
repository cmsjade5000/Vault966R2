"""A synthetic equivalent of observed schema; no live DB copy or application rows."""

from pathlib import Path
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.models.profile import Profile, ProfileCredential, MoviePreference
from api.services.credentials import build_profile_credential
from api.services.personal_schema_bridge import (
    BridgeError,
    FIXED_RESERVATIONS,
    OLD_VERSION,
    PHYSICAL_VERSION,
    NEW_VERSION,
    inspect_database,
    apply_bridge,
    collect_schema,
)
from api.services.profile_archive import prepare_personal_fresh_start, restore_profile_archive
from api.services.session import create_session_token, parse_session_token
from api.services.setup import (
    create_first_profile_setup,
    matching_db_credential_profile_id,
    create_personal_reviewer,
)
from api.services.setup_grants import (
    issue_setup_grant,
    bind_setup_grant,
    require_bound_setup_grant,
    SetupGrantError,
)

FIXTURE = Path(__file__).parent / "fixtures/vault966-prior-schema.sql"
PASSWORD = "synthetic-preserved-password-only"
CODE = "synthetic-private-code-bridge-only"
NONCE = "N" * 43


def previous_database(tmp_path):
    path = tmp_path / "synthetic-equivalent.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(FIXTURE.read_text())
        db.execute("INSERT INTO alembic_version(version_num) VALUES (?)", (OLD_VERSION,))
        for ident, role in [(1, "admin"), (2, "reviewer"), (3, "admin"), (4, "reviewer")]:
            db.execute(
                "INSERT INTO profiles(id,name,role) VALUES (?,?,?)",
                (ident, f"Synthetic original {ident}", role),
            )
        db.execute(
            "INSERT INTO app_setup(id,completed,owner_profile_id,completed_at) VALUES (1,true,1,'2026-01-01')"
        )
        for ident in range(1, 21):
            db.execute(
                "INSERT INTO movies(id,title,year,vault_id) VALUES (?,?,?,?)",
                (ident, f"Synthetic movie {ident}", 2000, f"S{ident:04}"),
            )
        counter = 0
        for profile in range(1, 5):
            for movie in range(1, 21):
                counter += 1
                if counter > 78:
                    continue
                db.execute(
                    "INSERT INTO movie_preferences(profile_id,movie_id,liked,watchlist) VALUES (?,?,?,?)",
                    (profile, movie, counter % 2 == 0, counter <= 11),
                )
        for ident in FIXED_RESERVATIONS:
            db.execute(
                "INSERT INTO retired_vault_ids(vault_id,source,reason) VALUES (?,?,?)",
                (ident, "legacy_gap", "synthetic original preserved reservation"),
            )
        db.execute(
            "INSERT INTO movie_flags(movie_id,reason,reported_by_profile_id,created_at,updated_at) VALUES (1,'synthetic',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        )
    # Stored credential hashes below are synthetic, never copied from live rows.
    engine = create_engine(f"sqlite:///{path}")
    # New ORM columns aren't present yet; use synthetic credential values directly.
    with engine.begin() as connection:
        for profile in [3, 4]:
            credential = build_profile_credential(
                profile_id=profile, access_key=f"Synthetic original {profile}", passcode=PASSWORD
            )
            connection.exec_driver_sql(
                "INSERT INTO profile_credentials(profile_id,access_key_salt,access_key_hash,passcode_salt,passcode_hash,kdf_name,kdf_iterations) VALUES (?,?,?,?,?,?,?)",
                (
                    profile,
                    credential.access_key_salt,
                    credential.access_key_hash,
                    credential.passcode_salt,
                    credential.passcode_hash,
                    credential.kdf_name,
                    credential.kdf_iterations,
                ),
            )
    engine.dispose()
    return path


def row_snapshot(db):
    # Tests only: full invented rows prove exact preservation of sensitive columns.
    tables = [
        "profiles",
        "profile_credentials",
        "app_setup",
        "movies",
        "movie_preferences",
        "movie_flags",
        "retired_vault_ids",
    ]
    return {table: db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall() for table in tables}


def test_verified_bridge_and_archive_restore_preserve_all_four_accounts_and_preferences(
    tmp_path, monkeypatch
):
    from api.config import settings

    monkeypatch.setattr(settings, "login_access_key", None)
    monkeypatch.setattr(settings, "login_passcode", None)
    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        rows = row_snapshot(db)
    result = apply_bridge(
        path, expected_version=before["version"], expected_sha=before["physical_schema_sha256"]
    )
    assert result["after_version"] == NEW_VERSION
    assert not result["archive_performed"] and not result["data_repair_performed"]
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == NEW_VERSION
        for table, original in rows.items():
            actual = db.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            if table in {"profiles", "app_setup"}:
                actual = [row[: len(original[0])] for row in actual]
            assert actual == original
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as db:
        old_roles = {p.id: p.role for p in db.query(Profile).all()}
        old_credentials = {c.profile_id: c.passcode_hash for c in db.query(ProfileCredential).all()}
        old_preferences = [
            (p.profile_id, p.movie_id, p.liked, p.watchlist)
            for p in db.query(MoviePreference).order_by(MoviePreference.id).all()
        ]
        old_tokens = {
            p.id: create_session_token(
                p.id,
                secret="synthetic-session-secret",
                ttl_seconds=3600,
                revision=p.session_revision,
            )
            for p in db.query(Profile).all()
        }
        batch = prepare_personal_fresh_start(db, expected_active_ids={1, 2, 3, 4})
        assert db.query(Profile).filter(Profile.archived_at.is_(None)).count() == 0
        assert db.query(MoviePreference).count() == 78
        assert db.query(MoviePreference).filter_by(watchlist=True).count() == 11
        issue_setup_grant(db, owner_name="Synthetic owner", code=CODE)
        bind_setup_grant(db, code=CODE, browser_nonce=NONCE)
        new = create_first_profile_setup(
            db,
            profile_name="Synthetic owner",
            access_key="Synthetic owner",
            passcode=PASSWORD,
            passcode_confirm=PASSWORD,
            bootstrap_browser_nonce=NONCE,
        ).profile
        replacement_id = new.id
        reviewer = create_personal_reviewer(
            db, profile_name="Synthetic reviewer", passcode=PASSWORD, passcode_confirm=PASSWORD
        )
        reviewer_id = reviewer.id
        replacement_ids = {replacement_id, reviewer_id}
        db.add_all(
            [
                MoviePreference(profile_id=replacement_id, movie_id=1, liked=True, watchlist=False),
                MoviePreference(profile_id=reviewer_id, movie_id=2, liked=False, watchlist=True),
            ]
        )
        db.commit()
        replacement_credentials = {
            c.profile_id: c.passcode_hash
            for c in db.query(ProfileCredential)
            .filter(ProfileCredential.profile_id.in_(replacement_ids))
            .all()
        }
        assert replacement_id > 4 and new.role == "admin"
        assert db.query(MoviePreference).filter_by(profile_id=replacement_id).count() == 1
        replacement_token = create_session_token(
            replacement_id,
            secret="synthetic-session-secret",
            ttl_seconds=3600,
            revision=new.session_revision,
        )
        replacement_batch = restore_profile_archive(
            db, batch_id=batch, expected_active_ids=replacement_ids
        )
        assert {
            p.id: p.role for p in db.query(Profile).filter(Profile.archived_at.is_(None)).all()
        } == old_roles
        assert {
            c.profile_id: c.passcode_hash
            for c in db.query(ProfileCredential)
            .filter(ProfileCredential.profile_id.in_([1, 2, 3, 4]))
            .all()
        } == old_credentials
        assert [
            (p.profile_id, p.movie_id, p.liked, p.watchlist)
            for p in db.query(MoviePreference)
            .filter(MoviePreference.profile_id.in_([1, 2, 3, 4]))
            .order_by(MoviePreference.id)
            .all()
        ] == old_preferences
        for ident, token in old_tokens.items():
            assert (
                db.get(Profile, ident).session_revision
                != parse_session_token(token, secret="synthetic-session-secret").revision
            )
        assert db.get(Profile, replacement_id).archived_at is not None
        assert db.get(Profile, reviewer_id).archived_at is not None
        assert (
            matching_db_credential_profile_id(db, access_key="Synthetic owner", passcode=PASSWORD)
            is None
        )
        assert (
            matching_db_credential_profile_id(
                db, access_key="Synthetic original 3", passcode=PASSWORD
            )
            == 3
        )
        assert (
            db.get(Profile, replacement_id).session_revision
            != parse_session_token(replacement_token, secret="synthetic-session-secret").revision
        )
        with pytest.raises(SetupGrantError):
            require_bound_setup_grant(db, browser_nonce=NONCE)
        restore_profile_archive(db, batch_id=replacement_batch, expected_active_ids={1, 2, 3, 4})
        assert db.get(Profile, replacement_id).archived_at is None
        assert {
            p.id: p.role for p in db.query(Profile).filter(Profile.archived_at.is_(None)).all()
        } == {replacement_id: "admin", reviewer_id: "reviewer"}
        assert {
            c.profile_id: c.passcode_hash
            for c in db.query(ProfileCredential)
            .filter(ProfileCredential.profile_id.in_(replacement_ids))
            .all()
        } == replacement_credentials
        assert db.query(MoviePreference).filter_by(profile_id=replacement_id).one().liked
        assert db.query(MoviePreference).filter_by(profile_id=reviewer_id).one().watchlist
        assert db.query(MoviePreference).count() == 80
        assert (
            matching_db_credential_profile_id(db, access_key="Synthetic owner", passcode=PASSWORD)
            == replacement_id
        )
        assert (
            matching_db_credential_profile_id(
                db, access_key="Synthetic reviewer", passcode=PASSWORD
            )
            == reviewer_id
        )
        assert (
            matching_db_credential_profile_id(
                db, access_key="Synthetic original 3", passcode=PASSWORD
            )
            is None
        )
        assert (
            db.get(Profile, replacement_id).session_revision
            != parse_session_token(replacement_token, secret="synthetic-session-secret").revision
        )
    engine.dispose()


@pytest.mark.parametrize("phase", ["before_stamp", "after_stamp", "after_ddl", "before_commit"])
def test_bridge_failure_rolls_back_ddl_stamp_and_rows(tmp_path, phase):
    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        rows = row_snapshot(db)
        schema = collect_schema(db)

    def fail(stage):
        if stage == phase:
            raise RuntimeError("synthetic interruption")

    with pytest.raises(RuntimeError):
        apply_bridge(
            path,
            expected_version=before["version"],
            expected_sha=before["physical_schema_sha256"],
            fault=fail,
        )
    with sqlite3.connect(path) as db:
        assert row_snapshot(db) == rows
        assert collect_schema(db) == schema
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == OLD_VERSION
        assert (
            db.execute("SELECT COUNT(*) FROM sqlite_schema WHERE name='setup_grants'").fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "change",
    [
        "stamp",
        "missing_index",
        "partial_index",
        "changed_type",
        "missing_fk",
        "seed_missing",
        "seed_source",
        "collision",
        "fingerprint",
    ],
)
def test_bridge_rejects_drift_without_any_writes(tmp_path, change):
    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        if change == "stamp":
            db.execute("UPDATE alembic_version SET version_num='unexpected'")
        elif change == "missing_index":
            db.execute("DROP INDEX ix_maintenance_jobs_state")
        elif change == "partial_index":
            db.execute("DROP INDEX ix_maintenance_jobs_state")
            db.execute(
                "CREATE INDEX ix_maintenance_jobs_state ON maintenance_jobs(state) WHERE state='queued'"
            )
        elif change == "changed_type":
            db.execute("ALTER TABLE profiles ADD COLUMN unexpected TEXT")
        elif change == "missing_fk":
            db.execute("DROP TABLE movie_flags")
            db.execute(
                "CREATE TABLE movie_flags(movie_id INTEGER PRIMARY KEY,reason TEXT,notes TEXT,created_at TIMESTAMP,updated_at TIMESTAMP,reported_by_profile_id INTEGER)"
            )
        elif change == "seed_missing":
            db.execute("DELETE FROM retired_vault_ids WHERE vault_id=?", (FIXED_RESERVATIONS[0],))
        elif change == "seed_source":
            db.execute(
                "UPDATE retired_vault_ids SET source='different' WHERE vault_id=?",
                (FIXED_RESERVATIONS[0],),
            )
        elif change == "collision":
            db.execute("UPDATE movies SET vault_id=? WHERE id=1", (FIXED_RESERVATIONS[0],))
    with sqlite3.connect(path) as db:
        schema = collect_schema(db)
        rows = row_snapshot(db)
    expected = "0" * 64 if change == "fingerprint" else before["physical_schema_sha256"]
    with pytest.raises(BridgeError):
        apply_bridge(path, expected_version=before["version"], expected_sha=expected)
    with sqlite3.connect(path) as db:
        assert collect_schema(db) == schema and row_snapshot(db) == rows


def test_already_current_physical_stamp_uses_additive_delta_without_bridge(tmp_path):
    path = previous_database(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE alembic_version SET version_num=?", (PHYSICAL_VERSION,))
    checked = inspect_database(path)
    result = apply_bridge(
        path, expected_version=PHYSICAL_VERSION, expected_sha=checked["physical_schema_sha256"]
    )
    assert (
        result["before"]["version"] == PHYSICAL_VERSION and result["after_version"] == NEW_VERSION
    )


def test_default_inspection_reads_schema_metadata_only(tmp_path, monkeypatch):
    import api.services.personal_schema_bridge as bridge

    path = previous_database(tmp_path)
    original = sqlite3.connect

    def metadata_connection(*args, **kwargs):
        connection = original(*args, **kwargs)

        def authorize(action, name, *_):
            if action == sqlite3.SQLITE_READ and name not in {
                "sqlite_master",
                "sqlite_schema",
                "alembic_version",
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(bridge.sqlite3, "connect", metadata_connection)
    checked = inspect_database(path)
    assert checked["version"] == OLD_VERSION
    assert checked["fixed_reservations_verified"] is False
    with pytest.raises(sqlite3.DatabaseError):
        inspect_database(path, verify_fixed_reservations=True)


@pytest.mark.parametrize(
    "change",
    [
        "missing_table",
        "nonunique_run_id",
        "fk_delete",
        "nullable",
        "default",
        "trigger",
        "collation",
        "expression",
        "generated",
        "multiple_stamps",
    ],
)
def test_bridge_rejects_semantic_schema_drift(tmp_path, change):
    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        if change == "missing_table":
            db.execute("DROP TABLE maintenance_jobs")
        elif change == "nonunique_run_id":
            db.execute("DROP INDEX ix_maintenance_jobs_run_id")
            db.execute("CREATE INDEX ix_maintenance_jobs_run_id ON maintenance_jobs(run_id)")
        elif change in {"fk_delete", "nullable", "default"}:
            table = "movie_flags" if change == "fk_delete" else "profile_credentials"
            sql = db.execute("SELECT sql FROM sqlite_schema WHERE name=?", (table,)).fetchone()[0]
            if change == "fk_delete":
                sql = sql.replace("ON DELETE SET NULL", "ON DELETE CASCADE")
            elif change == "nullable":
                sql = sql.replace(
                    "access_key_hash VARCHAR(128) NOT NULL", "access_key_hash VARCHAR(128)"
                )
            else:
                sql = sql.replace("DEFAULT 200000", "DEFAULT 123")
            rows = db.execute(f"SELECT * FROM {table}").fetchall()
            db.execute(f"DROP TABLE {table}")
            db.execute(sql)
            for row in rows:
                marks = ",".join("?" for _ in row)
                db.execute(f"INSERT INTO {table} VALUES ({marks})", row)
        elif change == "trigger":
            db.execute(
                "CREATE TRIGGER synthetic_trigger AFTER UPDATE ON alembic_version BEGIN SELECT 1; END"
            )
        elif change in {"collation", "expression"}:
            db.execute("DROP INDEX ix_maintenance_jobs_state")
            expression = "state COLLATE NOCASE" if change == "collation" else "lower(state)"
            db.execute(f"CREATE INDEX ix_maintenance_jobs_state ON maintenance_jobs({expression})")
        elif change == "generated":
            db.execute(
                "ALTER TABLE profiles ADD COLUMN synthetic_generated TEXT GENERATED ALWAYS AS (name) VIRTUAL"
            )
        else:
            db.execute("INSERT INTO alembic_version VALUES (?)", (PHYSICAL_VERSION,))
    with sqlite3.connect(path) as db:
        snapshot = db.execute("SELECT type,name,sql FROM sqlite_schema ORDER BY name").fetchall()
        rows = row_snapshot(db)
    with pytest.raises(BridgeError):
        apply_bridge(
            path, expected_version=before["version"], expected_sha=before["physical_schema_sha256"]
        )
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT type,name,sql FROM sqlite_schema ORDER BY name").fetchall()
            == snapshot
        )
        assert row_snapshot(db) == rows


def test_failure_during_additive_ddl_rolls_back_everything(tmp_path, monkeypatch):
    from alembic.operations import Operations

    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        rows, schema = row_snapshot(db), collect_schema(db)
    original = Operations.add_column

    def fail_after_column(self, table_name, column, **kwargs):
        original(self, table_name, column, **kwargs)
        if column.name == "archived_at":
            raise RuntimeError("synthetic DDL failure")

    monkeypatch.setattr(Operations, "add_column", fail_after_column)
    with pytest.raises(RuntimeError, match="DDL failure"):
        apply_bridge(
            path, expected_version=before["version"], expected_sha=before["physical_schema_sha256"]
        )
    with sqlite3.connect(path) as db:
        assert collect_schema(db) == schema and row_snapshot(db) == rows
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == OLD_VERSION


def test_wrong_additive_default_is_rejected_and_rolled_back(tmp_path, monkeypatch):
    from alembic.operations import Operations
    import sqlalchemy as sa

    path = previous_database(tmp_path)
    before = inspect_database(path)
    original = Operations.add_column

    def wrong_default(self, table_name, column, **kwargs):
        if column.name == "session_revision":
            column.server_default = sa.DefaultClause(sa.text("1"))
        return original(self, table_name, column, **kwargs)

    monkeypatch.setattr(Operations, "add_column", wrong_default)
    with pytest.raises(BridgeError, match="delta"):
        apply_bridge(
            path, expected_version=before["version"], expected_sha=before["physical_schema_sha256"]
        )
    assert inspect_database(path) == before


def test_abrupt_synthetic_process_exit_rolls_back_schema_and_stamp(tmp_path):
    import os
    import subprocess
    import sys

    path = previous_database(tmp_path)
    before = inspect_database(path)
    with sqlite3.connect(path) as db:
        schema, rows = collect_schema(db), row_snapshot(db)
    script = """from pathlib import Path
import os, sys
from api.services.personal_schema_bridge import apply_bridge
def stop(phase):
    if phase == 'after_ddl':
        os._exit(23)
apply_bridge(Path(sys.argv[1]),expected_version=sys.argv[2],expected_sha=sys.argv[3],fault=stop)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(path),
            before["version"],
            before["physical_schema_sha256"],
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DATABASE_URL": "sqlite://", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 23, result.stderr
    with sqlite3.connect(path) as db:
        assert collect_schema(db) == schema and row_snapshot(db) == rows
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == OLD_VERSION
