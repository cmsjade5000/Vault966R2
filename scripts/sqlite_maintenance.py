"""Check SQLite integrity and create validated, rotating online backups."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


DEFAULT_DATABASE = (
    pathlib.Path.home() / "Library" / "Application Support" / "Vault966" / "data" / "vault.db"
)
DEFAULT_BACKUP_DIR = (
    pathlib.Path.home() / "Library" / "Application Support" / "Vault966" / "backups"
)


class MaintenanceError(RuntimeError):
    """Raised when a maintenance operation cannot complete safely."""


@dataclass(frozen=True)
class IntegrityResult:
    database: str
    check: str
    healthy: bool
    messages: list[str]


@dataclass(frozen=True)
class BackupResult:
    source: str
    backup: str
    removed: list[str]


def _readonly_connection(database: pathlib.Path, timeout: float) -> sqlite3.Connection:
    try:
        resolved = database.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise MaintenanceError(f"Database does not exist: {database}") from exc
    if not resolved.is_file():
        raise MaintenanceError(f"Database is not a regular file: {database}")

    connection = sqlite3.connect(
        f"{resolved.as_uri()}?mode=ro",
        uri=True,
        timeout=timeout,
    )
    connection.execute("PRAGMA query_only=ON")
    connection.execute(f"PRAGMA busy_timeout={max(0, int(timeout * 1000))}")
    return connection


def check_database(
    database: pathlib.Path,
    *,
    quick: bool = False,
    max_errors: int = 100,
    timeout: float = 15.0,
) -> IntegrityResult:
    """Run a read-only SQLite integrity check without changing the database."""
    if max_errors < 1:
        raise MaintenanceError("max_errors must be at least 1")
    if timeout < 0:
        raise MaintenanceError("timeout must not be negative")

    check_name = "quick_check" if quick else "integrity_check"
    try:
        with _readonly_connection(database, timeout) as connection:
            rows = connection.execute(f"PRAGMA {check_name}({max_errors})").fetchall()
        messages = [str(row[0]) for row in rows]
    except sqlite3.DatabaseError as exc:
        messages = [f"database error: {exc}"]
    return IntegrityResult(
        database=str(database.expanduser()),
        check=check_name,
        healthy=messages == ["ok"],
        messages=messages,
    )


def _fsync_file(path: pathlib.Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: pathlib.Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_database_files(path: pathlib.Path) -> None:
    path.unlink(missing_ok=True)
    pathlib.Path(f"{path}-wal").unlink(missing_ok=True)
    pathlib.Path(f"{path}-shm").unlink(missing_ok=True)


def _backup_filename(database: pathlib.Path, now: datetime) -> str:
    timestamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{database.stem}-{timestamp}.db"


def _rotate_backups(
    backup_dir: pathlib.Path,
    *,
    database_stem: str,
    keep: int,
) -> list[pathlib.Path]:
    completed = sorted(
        (
            path
            for path in backup_dir.glob(f"{database_stem}-*.db")
            if path.is_file() and not path.name.startswith(".")
        ),
        key=lambda path: path.name,
        reverse=True,
    )
    removed: list[pathlib.Path] = []
    for expired in completed[keep:]:
        expired.unlink()
        removed.append(expired)
    if removed:
        _fsync_directory(backup_dir)
    return sorted(removed, key=lambda path: path.name)


def create_backup(
    database: pathlib.Path,
    backup_dir: pathlib.Path,
    *,
    keep: int = 7,
    timeout: float = 15.0,
    pages_per_step: int = 256,
    sleep_seconds: float = 0.05,
    now: datetime | None = None,
) -> BackupResult:
    """Create, validate, atomically publish, and rotate an online SQLite backup."""
    if keep < 1:
        raise MaintenanceError("keep must be at least 1")
    if pages_per_step < 1:
        raise MaintenanceError("pages_per_step must be at least 1")
    if sleep_seconds < 0:
        raise MaintenanceError("sleep_seconds must not be negative")

    source = database.expanduser().resolve()
    destination_dir = backup_dir.expanduser().resolve()
    preflight = check_database(source, quick=True, timeout=timeout)
    if not preflight.healthy:
        raise MaintenanceError(
            "Source database failed quick_check; backup and rotation were skipped"
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_name = _backup_filename(source, now or datetime.now(timezone.utc))
    final_path = destination_dir / backup_name
    if final_path.exists():
        raise MaintenanceError(f"Backup already exists: {final_path}")
    temporary_path = destination_dir / f".{backup_name}.partial-{os.getpid()}"

    try:
        with _readonly_connection(source, timeout) as source_connection:
            with sqlite3.connect(temporary_path, timeout=timeout) as destination_connection:
                source_connection.backup(
                    destination_connection,
                    pages=pages_per_step,
                    sleep=sleep_seconds,
                )
                destination_connection.execute("PRAGMA journal_mode=DELETE")
        os.chmod(temporary_path, 0o600)

        verification = check_database(temporary_path, timeout=timeout)
        if not verification.healthy:
            raise MaintenanceError("Completed backup failed integrity_check")

        _fsync_file(temporary_path)
        os.replace(temporary_path, final_path)
        _fsync_directory(destination_dir)
    except (OSError, sqlite3.DatabaseError) as exc:
        raise MaintenanceError(f"Backup failed: {exc}") from exc
    finally:
        _remove_database_files(temporary_path)

    removed = _rotate_backups(
        destination_dir,
        database_stem=source.stem,
        keep=keep,
    )
    return BackupResult(
        source=str(source),
        backup=str(final_path),
        removed=[str(path) for path in removed],
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _nonnegative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Run a read-only integrity check")
    check_parser.add_argument("--database", type=pathlib.Path, default=DEFAULT_DATABASE)
    check_parser.add_argument(
        "--quick",
        action="store_true",
        help="Use PRAGMA quick_check instead of the full PRAGMA integrity_check.",
    )
    check_parser.add_argument("--max-errors", type=_positive_int, default=100)
    check_parser.add_argument("--timeout", type=_nonnegative_float, default=15.0)

    backup_parser = subparsers.add_parser(
        "backup",
        help="Create a validated online backup and rotate older completed backups",
    )
    backup_parser.add_argument("--database", type=pathlib.Path, default=DEFAULT_DATABASE)
    backup_parser.add_argument("--backup-dir", type=pathlib.Path, default=DEFAULT_BACKUP_DIR)
    backup_parser.add_argument("--keep", type=_positive_int, default=7)
    backup_parser.add_argument("--timeout", type=_nonnegative_float, default=15.0)
    backup_parser.add_argument("--pages-per-step", type=_positive_int, default=256)
    backup_parser.add_argument("--sleep-seconds", type=_nonnegative_float, default=0.05)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "check":
            result = check_database(
                args.database,
                quick=args.quick,
                max_errors=args.max_errors,
                timeout=args.timeout,
            )
            print(json.dumps(asdict(result), sort_keys=True))
            return 0 if result.healthy else 1

        result = create_backup(
            args.database,
            args.backup_dir,
            keep=args.keep,
            timeout=args.timeout,
            pages_per_step=args.pages_per_step,
            sleep_seconds=args.sleep_seconds,
        )
        print(json.dumps(asdict(result), sort_keys=True))
        return 0
    except MaintenanceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
