import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _rules(path: Path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


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


def test_docker_context_excludes_private_and_nonruntime_artifacts() -> None:
    dockerignore_rules = _rules(ROOT / ".dockerignore")
    required_rules = {
        ".git",
        ".agents/",
        ".codex/",
        ".codex-log/",
        "AGENTS.md",
        "skills/",
        "data/",
        "reports/",
        "legacy/data/",
        "legacy/reports/",
        "board-companion/",
        "**/board-companion/",
        "**/*[Bb]oard*[Ss]napshot*",
        "**/*[Bb]oard*[Aa]rtifact*",
        "*.zip",
        "**/*.zip",
        "*.tar",
        "**/*.tar",
        "*.tar.gz",
        "**/*.tar.gz",
        "*.tgz",
        "**/*.tgz",
        "*.7z",
        "**/*.7z",
        "*.rar",
        "**/*.rar",
    }

    assert required_rules <= dockerignore_rules


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
