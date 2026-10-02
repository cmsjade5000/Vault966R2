"""Release safety checks use tiny disposable repositories and synthetic databases."""

import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tarfile

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from sqlalchemy import create_engine

from api.db import Base
from scripts import vault_release as release


@pytest.fixture
def artifact_repo(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    files = {
        "alembic.ini": "[alembic]\nscript_location = alembic\n",
        "api/main.py": "answer = 42\n",
        "requirements.txt": "example==1.0\n",
        "requirements.lock": "example==1.0\n",
        "release-schema.json": json.dumps(
            {"format": 1, "tables": {"movies": ["id"]}, "movie_unique_indexes": {}}
        ),
        "alembic/versions/a.py": 'revision: str = "a"\ndown_revision = None\n',
        "alembic/versions/b.py": 'revision: str = "b"\ndown_revision: str = "a"\n',
        ".env": "SYNTHETIC_SECRET=not-a-real-secret\n",
        "board-companion/public/catalog.board.json": '{"synthetic":true}\n',
    }
    for name, contents in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    for args in (
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    monkeypatch.setattr(release, "ROOT", root)
    artifact = tmp_path / "release.tar.gz"
    manifest = release.build(artifact)
    return artifact, manifest


def test_build_is_reproducible_and_excludes_runtime_data(artifact_repo, tmp_path):
    artifact, manifest = artifact_repo
    second = tmp_path / "another-name.tar.gz"
    assert release.build(second) == manifest
    assert artifact.read_bytes() == second.read_bytes()
    checked, entries = release.read_artifact(artifact)
    assert checked["alembic_heads"] == ["b"]
    assert not any("board-companion" in name or ".env" in name for name in entries)


def test_build_rejects_uncommitted_source(artifact_repo, tmp_path):
    (release.ROOT / "api/main.py").write_text("changed = True\n")
    with pytest.raises(release.ReleaseError, match="Commit"):
        release.build(tmp_path / "new.tar.gz")


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("app/api/link", tarfile.SYMTYPE),
    ],
)
def test_verify_rejects_unsafe_archive_members(tmp_path, name, kind):
    artifact = tmp_path / "unsafe.tar.gz"
    with tarfile.open(artifact, "w:gz") as archive:
        info = tarfile.TarInfo(name)
        info.type = kind
        info.size = 1 if kind == tarfile.REGTYPE else 0
        archive.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(release.ReleaseError, match="Unsafe"):
        release.read_artifact(artifact)


def test_verify_rejects_payload_tampering(artifact_repo, tmp_path):
    artifact, _ = artifact_repo
    changed = tmp_path / "tampered.tar.gz"
    with tarfile.open(artifact, "r:gz") as source, tarfile.open(changed, "w:gz") as target:
        for info in source:
            value = source.extractfile(info).read()
            if info.name == "app/api/main.py":
                value = b"answer = 0\n"
                info.size = len(value)
            target.addfile(info, io.BytesIO(value))
    with pytest.raises(release.ReleaseError, match="Payload verification"):
        release.read_artifact(changed)


@pytest.fixture
def staged(artifact_repo, tmp_path, monkeypatch):
    artifact, _ = artifact_repo
    support = tmp_path / "support"
    inventory = {"python": "3.12.13", "packages": [["example", "1.0"]]}
    monkeypatch.setattr(release, "host_supported", lambda: True)
    monkeypatch.setattr(release, "runtime_inventory", lambda interpreter: inventory.copy())

    def fake_uv(args, **kwargs):
        if args[:2] == ["uv", "venv"]:
            venv = Path(args[-1])
            (venv / "bin").mkdir(parents=True)
            (venv / "bin/python").write_text("synthetic-interpreter")
        elif args[:3] == ["uv", "pip", "sync"]:
            pass
        else:
            raise AssertionError(args)
        return ""

    monkeypatch.setattr(release, "run", fake_uv)
    digest = release.digest(artifact.read_bytes())
    path = release.stage(artifact, support, "fixture-python", digest)
    return path, support, artifact, digest


def test_stage_is_idempotent_and_attests_runtime(staged):
    path, support, artifact, digest = staged
    assert release.stage(artifact, support, "fixture-python", digest) == path
    (path / ".venv/bin/python").write_text("changed-runtime")
    with pytest.raises(release.ReleaseError, match="Staged runtime"):
        release.verify_staged(path)


def test_stage_rejects_unreviewed_digest_before_writing(artifact_repo, tmp_path, monkeypatch):
    artifact, _ = artifact_repo
    support = tmp_path / "no-write"
    monkeypatch.setattr(release, "host_supported", lambda: True)
    with pytest.raises(release.ReleaseError, match="Artifact SHA256"):
        release.stage(artifact, support, "unused", "0" * 64)
    assert not support.exists()


def test_schema_contract_matches_current_models():
    contract = json.loads((Path(__file__).resolve().parents[1] / "release-schema.json").read_text())
    assert contract["tables"] == {
        table.name: sorted(column.name for column in table.columns)
        for table in Base.metadata.sorted_tables
    }
    assert contract["movie_unique_indexes"] == {
        index.name: [column.name for column in index.columns]
        for index in Base.metadata.tables["movies"].indexes
        if index.unique
    }


def test_runtime_and_test_locks_agree_with_direct_requirements():
    root = Path(__file__).resolve().parents[1]
    runtime = release.locked_packages(root / "requirements.lock")
    development = release.locked_packages(root / "requirements-dev.lock")
    assert all(development.get(name) == version for name, version in runtime.items())
    for line in (root / "requirements.txt").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        required = Requirement(line.split("#", 1)[0].strip())
        assert runtime[canonicalize_name(required.name)] in required.specifier


def test_stage_rejects_extra_or_symlinked_payload(staged):
    path, _, _, _ = staged
    extra = path / "app/api/extra.py"
    extra.write_text("unexpected = True\n")
    with pytest.raises(release.ReleaseError, match="file set changed"):
        release.verify_staged(path)
    extra.rename(path / "untracked-extra-preserved")
    original = path / "app/api/main.py"
    original.rename(path / "original.py")
    original.symlink_to(path / "original.py")
    with pytest.raises(release.ReleaseError, match="Staged payload"):
        release.verify_staged(path)


def test_live_target_requires_explicit_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(release, "LIVE_SUPPORT", tmp_path / "live")
    with pytest.raises(release.ReleaseError, match="explicit"):
        release.check_target(tmp_path / "live", False)
    assert not (tmp_path / "live").exists()


@pytest.mark.parametrize("allow_live", [False, True])
def test_live_descendants_cannot_be_used_as_disposable_support_roots(
    tmp_path, monkeypatch, allow_live
):
    monkeypatch.setattr(release, "LIVE_SUPPORT", tmp_path / "live")
    for child in ("app", "releases", "data/nested"):
        with pytest.raises(release.ReleaseError, match="descendant"):
            release.check_target(tmp_path / "live" / child, allow_live)
    assert not (tmp_path / "live").exists()


def test_stage_cli_has_no_default_support_target():
    result = subprocess.run(
        [__import__("sys").executable, str(Path(release.__file__)), "stage"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "--support-dir" in result.stderr


def test_schema_check_does_not_change_database_and_rejects_drift(tmp_path):
    database = tmp_path / "fixture.sqlite"
    fixture_engine = create_engine("sqlite:///" + str(database))
    Base.metadata.create_all(fixture_engine)
    fixture_engine.dispose()
    before = database.read_bytes()
    release.schema_check(database, Path(__file__).resolve().parents[1] / "release-schema.json")
    assert database.read_bytes() == before
    with sqlite3.connect(database) as db:
        db.execute("DROP TABLE usage_events")
    before = database.read_bytes()
    with pytest.raises(release.ReleaseError, match="usage_events"):
        release.schema_check(database, Path(__file__).resolve().parents[1] / "release-schema.json")
    assert database.read_bytes() == before


@pytest.fixture
def previous_installation(staged):
    path, support, _, _ = staged
    (support / "app/api").mkdir(parents=True)
    (support / "app/api/previous.py").write_text("previous = True\n")
    (support / "app/.env").write_text("SYNTHETIC_ONLY=fixture\n")
    (support / ".venv").mkdir()
    (support / ".venv/previous").write_text("old-runtime")
    (support / "data").mkdir()
    database = support / "data/vault.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE movies (id INTEGER PRIMARY KEY)")
        db.execute("INSERT INTO movies VALUES (1)")
    before = database.read_bytes()
    previous = release.fingerprint(support / "app")
    return path, support, database, before, previous


def test_activation_and_rollback_preserve_data_credentials_and_old_runtime(previous_installation):
    path, support, database, before, previous = previous_installation
    with pytest.raises(release.ReleaseError, match="Stop all"):
        release.activate(path, support, previous, False, False)
    with pytest.raises(release.ReleaseError, match="Current deployment"):
        release.activate(path, support, "0" * 64, True, False)
    receipt = release.activate(path, support, previous, True, False)
    assert (support / "app").is_symlink()
    assert (support / "app/.env").read_text() == "SYNTHETIC_ONLY=fixture\n"
    assert database.read_bytes() == before
    release.rollback(receipt, True, False)
    assert not (support / "app").is_symlink()
    assert (support / ".venv/previous").read_text() == "old-runtime"
    assert (support / "app/.env").read_text() == "SYNTHETIC_ONLY=fixture\n"
    assert database.read_bytes() == before


def test_receipt_failure_leaves_active_paths_and_runtime_bindings_untouched(
    previous_installation, monkeypatch
):
    path, support, database, before, previous = previous_installation
    original_write = Path.write_text

    def fail_receipt(target, *args, **kwargs):
        if target.name == "receipt.json":
            raise OSError("synthetic receipt failure")
        return original_write(target, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_receipt)
    with pytest.raises(OSError, match="synthetic receipt failure"):
        release.activate(path, support, previous, True, False)
    assert not (support / "app").is_symlink()
    assert (support / ".venv/previous").read_text() == "old-runtime"
    assert release.fingerprint(support / "app") == previous
    assert not (path / "app/.env").exists()
    assert not (path / "app/vault.db").is_symlink()
    assert database.read_bytes() == before


def test_runtime_pointer_move_failure_restores_previous_paths(previous_installation, monkeypatch):
    path, support, database, before, previous = previous_installation
    original_rename = Path.rename

    def fail_runtime_move(target, *args, **kwargs):
        if target == support / ".venv":
            raise OSError("synthetic pointer failure")
        return original_rename(target, *args, **kwargs)

    monkeypatch.setattr(Path, "rename", fail_runtime_move)
    with pytest.raises(OSError, match="synthetic pointer failure"):
        release.activate(path, support, previous, True, False)
    assert release.fingerprint(support / "app") == previous
    assert not (support / "app").is_symlink()
    assert (support / ".venv/previous").read_text() == "old-runtime"
    assert database.read_bytes() == before


def test_release_startup_checks_full_schema_without_bootstrap(tmp_path, monkeypatch):
    from api import db

    fixture_engine = create_engine("sqlite:///" + str(tmp_path / "fixture.sqlite"))
    Base.metadata.create_all(fixture_engine)
    monkeypatch.setattr(db, "engine", fixture_engine)
    monkeypatch.setenv("VAULT_SQLITE_SCHEMA_MODE", "verify")
    assert not db.should_bootstrap_sqlite_schema()
    db.verify_release_sqlite_schema()
    with fixture_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE usage_events")
    with pytest.raises(RuntimeError, match="usage_events"):
        db.verify_release_sqlite_schema()
    assert "usage_events" not in __import__("sqlalchemy").inspect(fixture_engine).get_table_names()
    fixture_engine.dispose()


def test_release_startup_rejects_wrong_database_binding_before_connecting(tmp_path, monkeypatch):
    from api import db

    app_root = tmp_path / "release/app"
    (app_root / "api").mkdir(parents=True)
    (app_root.parent / "release-manifest.json").write_text("{}")
    fixture_database = tmp_path / "fixture.sqlite"
    fixture_engine = create_engine("sqlite:///" + str(fixture_database))
    Base.metadata.create_all(fixture_engine)
    fixture_engine.dispose()
    before = fixture_database.read_bytes()
    monkeypatch.setattr(db, "__file__", str(app_root / "api/db.py"))
    monkeypatch.setattr(db, "engine", fixture_engine)
    with pytest.raises(RuntimeError, match="database binding"):
        db.verify_release_sqlite_schema()
    assert fixture_database.read_bytes() == before
    (app_root / "vault.db").symlink_to(fixture_database)
    db.verify_release_sqlite_schema()
    fixture_engine.dispose()
