import fnmatch
import os
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _dockerignore_rules() -> list[tuple[str, bool]]:
    rules = []
    for raw_line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        rules.append((pattern.strip("/"), negated))
    return rules


def _docker_context_includes(relative_path: str) -> bool:
    path = relative_path.strip("/")
    included = True
    for pattern, negated in _dockerignore_rules():
        if fnmatch.fnmatchcase(path, pattern):
            included = negated
    return included


def _docker_copy_contracts() -> list[tuple[tuple[str, ...], str]]:
    contracts = []
    for raw_line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("COPY "):
            continue
        tokens = shlex.split(line)
        assert len(tokens) >= 3
        assert not tokens[1].startswith("--")
        contracts.append((tuple(tokens[1:-1]), tokens[-1]))
    return contracts


def _stage_copy_source(runtime_root: Path, source: str, destination: str) -> None:
    source_path = ROOT / source
    destination_path = runtime_root / destination.removeprefix("./")
    if source_path.is_dir():
        for candidate in source_path.rglob("*"):
            if not candidate.is_file():
                continue
            relative_context_path = candidate.relative_to(ROOT).as_posix()
            if not _docker_context_includes(relative_context_path):
                continue
            target = destination_path / candidate.relative_to(source_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate, target)
        return

    assert source_path.is_file()
    assert _docker_context_includes(source)
    target = destination_path / source_path.name if destination.endswith("/") else destination_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target)


def test_local_env_files_are_ignored_but_example_remains_tracked() -> None:
    local_env = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", ".env.local"],
        cwd=ROOT,
        check=False,
    )
    example_env = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", ".env.example"],
        cwd=ROOT,
        check=False,
    )
    tracked_example = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env.example"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert local_env.returncode == 0
    assert example_env.returncode == 1
    assert tracked_example.returncode == 0


def test_docker_context_allowlist_excludes_unrelated_sentinels(tmp_path: Path) -> None:
    synthetic_context = tmp_path / "context"
    allowed = {
        "Dockerfile",
        ".dockerignore",
        "requirements.txt",
        "alembic.ini",
        "alembic/env.py",
        "api/main.py",
        "core/moods.py",
        "static/js/base.js",
        "templates/base.html",
        "scripts/normalize_genres.py",
    }
    excluded = {
        ".env.local",
        "arbitrary-untracked-sentinel.txt",
        "docs/arbitrary-untracked-sentinel.md",
        "data/private-export.csv",
        "reports/private-report.md",
        "board-companion/private-artifact.zip",
        "scripts/unrelated-maintenance.py",
        "core/agents.md",
        "api/__pycache__/main.pyc",
    }
    for relative_path in allowed | excluded:
        sentinel = synthetic_context / relative_path
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("synthetic sentinel\n", encoding="utf-8")

    included = {
        path.relative_to(synthetic_context).as_posix()
        for path in synthetic_context.rglob("*")
        if path.is_file()
        and _docker_context_includes(path.relative_to(synthetic_context).as_posix())
    }

    assert allowed <= included
    assert excluded.isdisjoint(included)


def test_docker_copy_allowlist_stages_runnable_runtime(tmp_path: Path) -> None:
    expected_contracts = [
        (("requirements.txt",), "./"),
        (("alembic.ini",), "./"),
        (("alembic",), "./alembic"),
        (("api",), "./api"),
        (("core",), "./core"),
        (("static",), "./static"),
        (("templates",), "./templates"),
        (("scripts/backfill_backdrops.py",), "./scripts/"),
        (("scripts/backfill_db_backup.py",), "./scripts/"),
        (("scripts/backfill_moods.py",), "./scripts/"),
        (("scripts/backfill_posters.py",), "./scripts/"),
        (("scripts/normalize_genres.py",), "./scripts/"),
        (("scripts/sqlite_maintenance.py",), "./scripts/"),
    ]
    contracts = _docker_copy_contracts()
    assert contracts == expected_contracts
    assert all("." not in sources for sources, _ in contracts)

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    for sources, destination in contracts:
        for source in sources:
            _stage_copy_source(runtime_root, source, destination)
    (runtime_root / "data").mkdir()
    (runtime_root / "reports").mkdir()

    assert not (runtime_root / "docs").exists()
    assert not (runtime_root / "core" / "agents.md").exists()
    assert "RUN mkdir -p data reports" in (ROOT / "Dockerfile").read_text(encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "ADMIN_TOKEN": "testtoken",
            "DATABASE_URL": "sqlite://",
            "DISABLE_AUTH": "true",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_CURRENT_TEST": "docker-runtime-contract",
            "PYTHONPATH": str(runtime_root),
        }
    )
    commands = [
        [
            sys.executable,
            "-c",
            "from fastapi.testclient import TestClient; from api.main import app; "
            "assert TestClient(app).get('/health').status_code == 200",
        ],
        [sys.executable, "-m", "alembic", "heads"],
        [sys.executable, "scripts/normalize_genres.py", "--help"],
        [sys.executable, "scripts/backfill_moods.py", "--help"],
        [sys.executable, "scripts/backfill_posters.py", "--help"],
        [sys.executable, "scripts/backfill_backdrops.py", "--help"],
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=runtime_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_quickstart_defaults_to_sqlite_and_uses_locked_node_install() -> None:
    example_values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert example_values["DATABASE_URL"] == "sqlite:///./vault.db"
    assert "SQLite is the default; no separate database service is required." in readme
    assert "npm ci" in readme
    assert "npm install" not in readme
    assert "npm ci" in contributing


def test_make_health_propagates_curl_failure(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_curl = bin_dir / "curl"
    fake_curl.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    fake_curl.chmod(fake_curl.stat().st_mode | stat.S_IXUSR)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["make", "health"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "API not responding on :8000" in result.stderr


def test_db_migrate_uses_disposable_api_container() -> None:
    result = subprocess.run(
        ["make", "--no-print-directory", "-n", "db.migrate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "docker compose run --rm --build api alembic upgrade head"
