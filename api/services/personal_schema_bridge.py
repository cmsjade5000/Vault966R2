"""Exact SQLite physical-schema bridge. No ordinary historical migration replay.

Read-only collection contains schema metadata and fixed reservation counts only.
Apply is maintenance-only, explicitly guarded and transaction tested. No HTTP API.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts/schema/vault966-prior-physical.json"
OLD_VERSION = "202606100008"
PHYSICAL_VERSION = "202607060001"
NEW_VERSION = "202610060001"
# Keep the exact reviewed constants from the historical migration; no private IDs.
FIXED_RESERVATIONS = (
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


class BridgeError(ValueError):
    pass


def collect_schema(db: sqlite3.Connection) -> dict:
    if db.execute(
        "SELECT 1 FROM sqlite_schema WHERE type IN ('trigger', 'view') LIMIT 1"
    ).fetchone():
        raise BridgeError("Unreviewed schema object; no bridge authorized")
    tables = [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    result = {}
    for table in tables:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", table):
            raise BridgeError("Unexpected schema identifier")
        if any(row[6] != 0 for row in db.execute(f'PRAGMA table_xinfo("{table}")')):
            raise BridgeError("Unreviewed hidden or generated column")
        columns = [list(row[1:]) for row in db.execute(f'PRAGMA table_info("{table}")')]
        indexes = []
        for row in db.execute(f'PRAGMA index_list("{table}")'):
            name = row[1]
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                raise BridgeError("Unexpected schema identifier")
            keys = [col for col in db.execute(f'PRAGMA index_xinfo("{name}")') if col[5]]
            if any(col[1] < 0 or col[3] != 0 or col[4] != "BINARY" for col in keys):
                raise BridgeError("Unreviewed index expression, order or collation")
            indexes.append(
                {
                    "name": name,
                    "unique": row[2],
                    "origin": row[3],
                    "partial": row[4],
                    "columns": [col[2] for col in db.execute(f'PRAGMA index_info("{name}")')],
                }
            )
        result[table] = {
            "columns": columns,
            "indexes": sorted(indexes, key=lambda x: x["name"]),
            "foreign_keys": sorted(
                [list(row[2:]) for row in db.execute(f'PRAGMA foreign_key_list("{table}")')]
            ),
        }
    return result


def schema_sha(schema: dict) -> str:
    return hashlib.sha256(
        json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def version(db: sqlite3.Connection) -> str:
    rows = db.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1 or rows[0][0] not in {OLD_VERSION, PHYSICAL_VERSION, NEW_VERSION}:
        raise BridgeError("Unexpected or multiple migration stamps")
    return rows[0][0]


def fixed_reservation_postcondition(db: sqlite3.Connection) -> None:
    marks = ",".join("?" for _ in FIXED_RESERVATIONS)
    present = db.execute(
        f"SELECT COUNT(*) FROM retired_vault_ids WHERE vault_id IN ({marks})", FIXED_RESERVATIONS
    ).fetchone()[0]
    legacy = db.execute(
        f"SELECT COUNT(*) FROM retired_vault_ids WHERE vault_id IN ({marks}) AND source='legacy_gap'",
        FIXED_RESERVATIONS,
    ).fetchone()[0]
    collisions = db.execute(
        f"SELECT COUNT(*) FROM movies WHERE vault_id IN ({marks})", FIXED_RESERVATIONS
    ).fetchone()[0]
    if (present, legacy, collisions) != (11, 11, 0):
        raise BridgeError(
            "Fixed historical reservation postcondition changed; no repair authorized"
        )


def preflight(
    db: sqlite3.Connection,
    *,
    expected_version: str | None = None,
    expected_sha: str | None = None,
    verify_fixed_reservations: bool = True,
) -> dict:
    actual_version = version(db)
    if actual_version not in {OLD_VERSION, PHYSICAL_VERSION} or (
        expected_version is not None and actual_version != expected_version
    ):
        raise BridgeError("Migration stamp changed; no bridge authorized")
    actual = collect_schema(db)
    baseline = json.loads(BASELINE.read_text())
    fingerprint = schema_sha(actual)
    if actual != baseline or (expected_sha is not None and fingerprint != expected_sha):
        raise BridgeError(
            "Physical schema differs from the reviewed baseline; no repair authorized"
        )
    if verify_fixed_reservations:
        fixed_reservation_postcondition(db)
    return {
        "version": actual_version,
        "physical_schema_sha256": fingerprint,
        "fixed_reservations_verified": verify_fixed_reservations,
    }


def inspect_database(path: Path, *, verify_fixed_reservations: bool = False) -> dict:
    if path.is_symlink() or not path.is_file():
        raise BridgeError("An existing regular database is required")
    with sqlite3.connect("file:" + quote(str(path.absolute())) + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        return preflight(db, verify_fixed_reservations=verify_fixed_reservations)


def apply_bridge(path: Path, *, expected_version: str, expected_sha: str, fault=None) -> dict:
    """Atomic SQLite stamp reconciliation + additive delta. Never archives profiles.

    Caller must stop writers and verify a private backup in the approved window.
    fault is solely for synthetic failure-injection tests; no CLI injection hook.
    """
    if path.is_symlink() or not path.is_file():
        raise BridgeError("An existing regular database is required")
    engine = create_engine(URL.create("sqlite", database=str(path.absolute())), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            db = connection.connection.driver_connection
            try:
                before = preflight(db, expected_version=expected_version, expected_sha=expected_sha)
                if (
                    db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                    or db.execute("PRAGMA foreign_key_check").fetchone() is not None
                ):
                    raise BridgeError("Database integrity gate failed")
                if fault:
                    fault("before_stamp")
                if before["version"] == OLD_VERSION:
                    changed = connection.exec_driver_sql(
                        "UPDATE alembic_version SET version_num=? WHERE version_num=?",
                        (PHYSICAL_VERSION, OLD_VERSION),
                    )
                    if changed.rowcount != 1:
                        raise BridgeError("Migration stamp changed")
                if fault:
                    fault("after_stamp")
                module_path = ROOT / "alembic/versions/202610060001_personal_sign_in.py"
                spec = importlib.util.spec_from_file_location(
                    "personal_additive_migration", module_path
                )
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                if fault:
                    fault("after_ddl")
                connection.exec_driver_sql(
                    "UPDATE alembic_version SET version_num=? WHERE version_num=?",
                    (NEW_VERSION, PHYSICAL_VERSION),
                )
                after = collect_schema(db)
                expected = json.loads(BASELINE.read_text())
                delta = json.loads(
                    (ROOT / "scripts/schema/vault966-personal-delta.json").read_text()
                )
                for table in ("profiles", "app_setup"):
                    expected[table]["columns"].extend(delta[table])
                for table in ("profile_archive_batches", "setup_grants"):
                    expected[table] = delta[table]
                if after != expected:
                    raise BridgeError("Candidate schema semantics differ from the reviewed delta")
                fixed_reservation_postcondition(db)
                if (
                    version(db) != NEW_VERSION
                    or db.execute("PRAGMA foreign_key_check").fetchone() is not None
                ):
                    raise BridgeError("Post-migration verification failed")
                result = {
                    "before": before,
                    "after_version": NEW_VERSION,
                    "after_physical_schema_sha256": schema_sha(after),
                    "archive_performed": False,
                    "data_repair_performed": False,
                }
                if fault:
                    fault("before_commit")
                connection.commit()
                return result
            except BaseException:
                connection.rollback()
                raise
    finally:
        engine.dispose()
