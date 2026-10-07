"""Build, attest and stage immutable macOS releases; activation is a separate gate."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from urllib.parse import quote
import uuid

ROOT = Path(__file__).resolve().parents[1]
LIVE_SUPPORT = Path.home() / "Library" / "Application Support" / "Vault966"
DIRECTORIES = ("api/", "core/", "templates/", "static/", "scripts/", "alembic/")
FILES = {"alembic.ini", "requirements.txt", "requirements.lock", "release-schema.json"}
MAX_BYTES = 128 * 1024 * 1024


class ReleaseError(ValueError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run(args: list[str], *, cwd: Path | None = None, env: dict | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd or ROOT, env=env, text=True).strip()


def runtime_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        name == str(path)
        and not path.is_absolute()
        and not any(part.startswith(".") or part == "__pycache__" for part in path.parts)
        and not any(part.endswith((".db", ".sqlite", ".pyc", ".log")) for part in path.parts)
        and (name in FILES or name.startswith(DIRECTORIES))
    )


def payload_identity(hashes: dict, modes: dict) -> str:
    return digest(json.dumps({"files": hashes, "modes": modes}, sort_keys=True).encode())


def validate_manifest(manifest: dict) -> None:
    hashes, modes = manifest["files"], manifest["modes"]
    if (
        manifest.get("format") != 1
        or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"])
        or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_tree"])
        or set(modes) != set(hashes)
        or not FILES.issubset(hashes)
        or any(
            not runtime_path(name) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for name, value in hashes.items()
        )
        or any(mode not in (0o644, 0o755) for mode in modes.values())
    ):
        raise ReleaseError("Invalid release manifest.")
    payload = payload_identity(hashes, modes)
    if (
        manifest["payload_sha256"] != payload
        or manifest["release_id"] != f"{manifest['source_commit'][:12]}-{payload[:12]}"
        or manifest["dependency_lock_sha256"] != hashes["requirements.lock"]
        or manifest["schema_contract_sha256"] != hashes["release-schema.json"]
        or manifest["python"] != "3.12"
        or manifest["platform"] != "darwin-arm64"
        or len(manifest["alembic_heads"]) != 1
    ):
        raise ReleaseError("Release identities disagree.")


def build(output: Path) -> dict:
    if run(["git", "status", "--porcelain"]):
        raise ReleaseError("Commit the candidate before building a release.")
    payload = {}
    modes = {}
    for row in run(["git", "ls-tree", "-r", "HEAD"]).splitlines():
        metadata, name = row.split("\t", 1)
        mode, kind, blob = metadata.split()
        if not runtime_path(name):
            continue
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ReleaseError(f"Runtime payload cannot contain links: {name}")
        payload[name] = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)
        modes[name] = 0o755 if mode == "100755" else 0o644
    if not FILES.issubset(payload):
        raise ReleaseError("Release requires its hashed lock and SQLite schema contract.")
    hashes = {name: digest(value) for name, value in sorted(payload.items())}
    payload_digest = payload_identity(hashes, modes)
    head = run(["git", "rev-parse", "HEAD"])
    revisions, parents = set(), set()
    for name, value in payload.items():
        if name.startswith("alembic/versions/") and name.endswith(".py"):
            for node in ast.parse(value).body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "revision",
                            "down_revision",
                        }:
                            item = ast.literal_eval(node.value)
                            if target.id == "revision":
                                revisions.add(item)
                            elif item:
                                parents.update(item if isinstance(item, tuple) else [item])
    manifest = {
        "format": 1,
        "release_id": f"{head[:12]}-{payload_digest[:12]}",
        "source_commit": head,
        "source_tree": run(["git", "rev-parse", "HEAD^{tree}"]),
        "payload_sha256": payload_digest,
        "python": "3.12",
        "platform": "darwin-arm64",
        "dependency_lock_sha256": hashes["requirements.lock"],
        "schema_contract_sha256": hashes["release-schema.json"],
        "alembic_heads": sorted(revisions - parents),
        "files": hashes,
        "modes": modes,
        "component": "main-macos-app",
        "exclusions": ["secrets", "databases", "logs", "private imports", "Board catalogs/assets"],
    }
    if len(manifest["alembic_heads"]) != 1:
        raise ReleaseError("Expected one Alembic head.")
    validate_manifest(manifest)
    with (
        output.open("xb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed,
    ):
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            entries = {
                "release-manifest.json": json.dumps(manifest, indent=2, sort_keys=True).encode()
            }
            entries.update({"app/" + name: value for name, value in payload.items()})
            for name, value in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(value)
                info.mode = modes.get(name.removeprefix("app/"), 0o644)
                archive.addfile(info, io.BytesIO(value))
    return manifest


def read_artifact(artifact: Path) -> tuple[dict, dict[str, tuple[bytes, int]]]:
    entries = {}
    total = 0
    with tarfile.open(artifact, "r:gz") as archive:
        for info in archive:
            path = PurePosixPath(info.name)
            if (
                not info.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or info.name in entries
                or info.name != str(path)
            ):
                raise ReleaseError("Unsafe or duplicate archive member.")
            total += info.size
            if total > MAX_BYTES:
                raise ReleaseError("Release exceeds the bounded payload size.")
            entries[info.name] = (archive.extractfile(info).read(), info.mode)
    manifest = json.loads(entries.pop("release-manifest.json")[0])
    validate_manifest(manifest)
    expected = manifest["files"]
    if set(entries) != {"app/" + name for name in expected}:
        raise ReleaseError("Release file set does not match its manifest.")
    for name, expected_hash in expected.items():
        if (
            digest(entries["app/" + name][0]) != expected_hash
            or entries["app/" + name][1] != manifest["modes"][name]
        ):
            raise ReleaseError(f"Payload verification failed: {name}")
    return manifest, entries


def check_target(support: Path, allow_live: bool) -> Path:
    support = support.absolute()
    if support.is_symlink():
        raise ReleaseError("Support root cannot be a symlink.")
    resolved, live = support.resolve(), LIVE_SUPPORT.resolve()
    if resolved != live and resolved.is_relative_to(live):
        raise ReleaseError("A live support descendant is not a valid release support root.")
    if resolved == live and not allow_live:
        raise ReleaseError("Live target requires explicit --allow-live-target approval.")
    return resolved


def plain_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ReleaseError(f"Expected a regular directory: {path}")


def runtime_fingerprint(venv: Path) -> str:
    plain_directory(venv)
    hashes = {}
    for path in sorted(venv.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            if path.parent != venv / "bin" or not path.name.startswith("python"):
                raise ReleaseError("Unexpected runtime symlink.")
            hashes[path.relative_to(venv).as_posix()] = digest(
                path.resolve(strict=True).read_bytes()
            )
        elif path.is_file():
            hashes[path.relative_to(venv).as_posix()] = digest(path.read_bytes())
    return digest(json.dumps(hashes, sort_keys=True).encode())


def runtime_inventory(interpreter: Path) -> dict:
    return json.loads(
        run(
            [
                str(interpreter),
                "-c",
                "import importlib.metadata as m,json,sys;"
                "print(json.dumps({'python':sys.version.split()[0],"
                "'packages':sorted((d.metadata['Name'],d.version) for d in m.distributions())}))",
            ]
        )
    )


def locked_packages(lock: Path) -> dict:
    return {
        re.sub(r"[-_.]+", "-", name).lower(): version
        for name, version in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)", lock.read_text(), re.M)
    }


def host_supported() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def check_stopped(support: Path, stopped: bool) -> None:
    if not stopped:
        raise ReleaseError("Stop all Vault jobs before changing app/runtime pointers.")
    if support.resolve() == LIVE_SUPPORT.resolve():
        for label in ("server", "watchdog", "maintenance"):
            result = subprocess.run(
                ["launchctl", "print", f"gui/{os.getuid()}/com.vault966.{label}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                raise ReleaseError("Vault launchd jobs are still loaded.")


def verify_staged(release: Path) -> dict:
    plain_directory(release)
    release = release.resolve()
    plain_directory(release / "app")
    manifest = json.loads((release / "release-manifest.json").read_text())
    validate_manifest(manifest)
    actual = {
        path.relative_to(release / "app").as_posix()
        for path in (release / "app").rglob("*")
        if path.is_file() and runtime_path(path.relative_to(release / "app").as_posix())
    }
    if actual != set(manifest["files"]):
        raise ReleaseError("Staged runtime file set changed.")
    for name, expected in manifest["files"].items():
        path = release / "app" / name
        if (
            any(parent.is_symlink() for parent in [path, *path.parents] if parent != release.parent)
            or not path.is_file()
            or digest(path.read_bytes()) != expected
            or path.stat().st_mode & 0o777 != manifest["modes"][name]
        ):
            raise ReleaseError(f"Staged payload changed: {name}")
    receipt = json.loads((release / "runtime-receipt.json").read_text())
    if receipt["dependency_lock_sha256"] != manifest["dependency_lock_sha256"] or receipt[
        "runtime_sha256"
    ] != runtime_fingerprint(release / ".venv"):
        raise ReleaseError("Staged runtime does not identify this dependency lock.")
    inventory = runtime_inventory(release / ".venv/bin/python")
    packages = {
        re.sub(r"[-_.]+", "-", name).lower(): version for name, version in inventory["packages"]
    }
    if (
        not inventory["python"].startswith("3.12.")
        or packages != locked_packages(release / "app/requirements.lock")
        or inventory["packages"] != receipt["packages"]
        or inventory["python"] != receipt["python"]
    ):
        raise ReleaseError("Installed runtime differs from the locked package inventory.")
    return manifest


def stage(
    artifact: Path, support: Path, python: str, expected_sha256: str, allow_live: bool = False
) -> Path:
    support = check_target(support, allow_live)
    if not host_supported():
        raise ReleaseError("This release lock targets macOS arm64, Python 3.12.")
    if digest(artifact.read_bytes()) != expected_sha256:
        raise ReleaseError("Artifact SHA256 differs from the reviewed release.")
    manifest, entries = read_artifact(artifact)
    release = support / "releases" / manifest["release_id"]
    plain_directory(support / "releases")
    plain_directory(release)
    if release.exists():
        verify_staged(release)
        return release
    release.mkdir(parents=True)
    for name, (value, mode) in entries.items():
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        path.chmod(mode & 0o777)
    (release / "release-manifest.json").write_text(json.dumps(manifest, indent=2))
    run(["uv", "venv", "--python", python, str(release / ".venv")])
    interpreter = release / ".venv/bin/python"
    run(
        [
            "uv",
            "pip",
            "sync",
            "--require-hashes",
            "--python",
            str(interpreter),
            str(release / "app/requirements.lock"),
        ]
    )
    inventory = runtime_inventory(interpreter)
    if not inventory["python"].startswith("3.12."):
        raise ReleaseError("Release requires Python 3.12.")
    inventory["dependency_lock_sha256"] = manifest["dependency_lock_sha256"]
    inventory["runtime_sha256"] = runtime_fingerprint(release / ".venv")
    (release / "runtime-receipt.json").write_text(json.dumps(inventory, indent=2))
    verify_staged(release)
    return release


def schema_check(database: Path, contract: Path, allow_live: bool = False) -> None:
    if database.is_symlink() or not database.is_file():
        raise ReleaseError("Schema check requires an existing regular database file.")
    if database.resolve() == (LIVE_SUPPORT / "data/vault.db").resolve() and not allow_live:
        raise ReleaseError("Live schema inspection requires explicit approval.")
    required = json.loads(contract.read_text())
    if required.get("format") != 1 or any(
        not re.fullmatch(r"[a-z][a-z0-9_]*", table) for table in required["tables"]
    ):
        raise ReleaseError("Invalid schema contract.")
    with sqlite3.connect("file:" + quote(str(database.absolute())) + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        for table, columns in required["tables"].items():
            existing = {row[1] for row in db.execute('PRAGMA table_info("' + table + '")')}
            if not set(columns).issubset(existing):
                raise ReleaseError(
                    f"Schema lacks required columns for {table}; no migration applied."
                )
        for index, columns in required["movie_unique_indexes"].items():
            indexes = {row[1] for row in db.execute('PRAGMA index_list("movies")') if row[2]}
            if index not in indexes:
                raise ReleaseError(f"Schema lacks unique index {index}; no migration applied.")
            actual = [
                row[2]
                for row in db.execute('PRAGMA index_info("' + index.replace('"', '""') + '")')
            ]
            if actual != columns:
                raise ReleaseError(
                    f"Schema index {index} covers different columns; no migration applied."
                )


def fingerprint(app: Path) -> str:
    hashes = {}
    for path in sorted(app.rglob("*")):
        name = path.relative_to(app).as_posix()
        if (
            path.is_file()
            and not path.is_symlink()
            and runtime_path(name)
            and "__pycache__" not in path.parts
        ):
            hashes[name] = digest(path.read_bytes())
    return digest(json.dumps(hashes, sort_keys=True).encode())


def activate(release: Path, support: Path, expected: str, stopped: bool, allow_live: bool) -> Path:
    support = check_target(support, allow_live)
    check_stopped(support, stopped)
    plain_directory(release)
    release = release.resolve()
    manifest = verify_staged(release)
    if release.resolve() != (support / "releases" / manifest["release_id"]).resolve():
        raise ReleaseError("Release is outside this support root.")
    app, venv = support / "app", support / ".venv"
    if not app.exists() or not venv.exists() or fingerprint(app) != expected:
        raise ReleaseError("Current deployment changed or rollback resources are missing.")
    previous_runtime = runtime_fingerprint(venv.resolve())
    schema_check(support / "data/vault.db", release / "app/release-schema.json", allow_live)
    plain_directory(support / "rollback")
    if (release / "app/.env").exists() or (release / "app/vault.db").is_symlink():
        raise ReleaseError("Release already has runtime bindings; inspect before reactivation.")
    if (app / ".env").is_symlink():
        raise ReleaseError("Credential file must be regular.")
    backup = support / "rollback" / (manifest["release_id"] + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, mode=0o700)
    receipt = {
        "support": str(support),
        "release": str(release),
        "previous_app_sha256": expected,
        "previous_runtime_sha256": previous_runtime,
    }
    receipt_path = backup / "receipt.json"
    # Persist rollback evidence before touching credentials, bindings or active paths.
    receipt_path.write_text(json.dumps(receipt, indent=2))
    receipt_path.chmod(0o600)
    with receipt_path.open("rb") as stream:
        os.fsync(stream.fileno())
    if (app / ".env").is_file():
        shutil.copy2(app / ".env", release / "app/.env")
        (release / "app/.env").chmod(0o600)
    (release / "app/vault.db").symlink_to(support / "data/vault.db")
    app.rename(backup / "app")
    try:
        venv.rename(backup / ".venv")
        app.symlink_to(release / "app", target_is_directory=True)
        venv.symlink_to(release / ".venv", target_is_directory=True)
    except Exception:
        for pointer in (app, venv):
            if pointer.is_symlink():
                pointer.rename(backup / (pointer.name + ".failed-link"))
        (backup / "app").rename(app)
        if (backup / ".venv").exists():
            (backup / ".venv").rename(venv)
        raise
    return receipt_path


def rollback(receipt: Path, stopped: bool, allow_live: bool) -> None:
    data = json.loads(receipt.read_text())
    support = check_target(Path(data["support"]), allow_live)
    check_stopped(support, stopped)
    backup = receipt.parent
    if (
        backup.parent != support / "rollback"
        or fingerprint(backup / "app") != data["previous_app_sha256"]
        or runtime_fingerprint((backup / ".venv").resolve()) != data["previous_runtime_sha256"]
    ):
        raise ReleaseError("Rollback receipt or preserved code does not match.")
    release = Path(data["release"])
    for name in ("app", ".venv"):
        pointer = support / name
        if not pointer.is_symlink() or pointer.resolve() != (release / name).resolve():
            raise ReleaseError("Current deployment differs from this rollback receipt.")
    restored = []
    try:
        for name in ("app", ".venv"):
            (support / name).rename(backup / (name + ".candidate-link"))
            try:
                (backup / name).rename(support / name)
            except Exception:
                (backup / (name + ".candidate-link")).rename(support / name)
                raise
            restored.append(name)
    except Exception:
        for name in reversed(restored):
            (support / name).rename(backup / name)
            (backup / (name + ".candidate-link")).rename(support / name)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("verify")
    p.add_argument("--artifact", type=Path, required=True)
    p = sub.add_parser("verify-staged")
    p.add_argument("--release", type=Path, required=True)
    p = sub.add_parser("stage")
    p.add_argument("--artifact", type=Path, required=True)
    p.add_argument("--support-dir", type=Path, required=True)
    p.add_argument("--python", default=sys.executable)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--allow-live-target", action="store_true")
    p = sub.add_parser("fingerprint")
    p.add_argument("--app", type=Path, required=True)
    p = sub.add_parser("schema-check")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--allow-live-target", action="store_true")
    p = sub.add_parser("activate")
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--support-dir", type=Path, required=True)
    p.add_argument("--expected-current", required=True)
    p.add_argument("--stopped", action="store_true")
    p.add_argument("--allow-live-target", action="store_true")
    p = sub.add_parser("rollback")
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--stopped", action="store_true")
    p.add_argument("--allow-live-target", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "build":
            print(json.dumps(build(args.output), indent=2))
        elif args.command == "verify":
            print(json.dumps(read_artifact(args.artifact)[0], indent=2))
        elif args.command == "verify-staged":
            print(json.dumps(verify_staged(args.release), indent=2))
        elif args.command == "stage":
            print(
                stage(
                    args.artifact,
                    args.support_dir,
                    args.python,
                    args.expected_sha256,
                    args.allow_live_target,
                )
            )
        elif args.command == "fingerprint":
            print(fingerprint(args.app))
        elif args.command == "schema-check":
            schema_check(args.database, args.contract, args.allow_live_target)
            print("Schema compatible; no migration applied.")
        elif args.command == "activate":
            print(
                activate(
                    args.release,
                    args.support_dir,
                    args.expected_current,
                    args.stopped,
                    args.allow_live_target,
                )
            )
        elif args.command == "rollback":
            rollback(args.receipt, args.stopped, args.allow_live_target)
            print("Previous code/runtime restored; database unchanged.")
    except (
        ReleaseError,
        OSError,
        KeyError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        parser.exit(1, f"Release blocked: {exc}\n")


if __name__ == "__main__":
    main()
