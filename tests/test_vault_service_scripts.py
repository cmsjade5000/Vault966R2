import os
import shutil
import stat
import subprocess
import textwrap
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "vault_runtime.sh"
SERVICE = ROOT / "scripts" / "vault_service.sh"
WATCHDOG = ROOT / "scripts" / "vault_watchdog.sh"


def write_executable(path: Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents))
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def runtime_env(tmp_path: Path, python_script: str, curl_exit: int) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    write_executable(python, python_script)
    write_executable(
        bin_dir / "curl",
        f"""\
        #!/usr/bin/env bash
        exit {curl_exit}
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PYTHON": str(python),
            "STARTUP_GRACE": "0",
            "HEALTH_INTERVAL": "0.05",
            "HEALTH_FAILURE_LIMIT": "1",
            "SHUTDOWN_GRACE": "1",
            "SUPERVISOR_INTERVAL": "0.05",
        }
    )
    return env


def test_runtime_terminates_unhealthy_child_to_exit(tmp_path: Path) -> None:
    env = runtime_env(
        tmp_path,
        """\
        #!/usr/bin/env bash
        trap '' TERM
        while true; do :; done
        """,
        curl_exit=1,
    )

    started = time.monotonic()
    result = subprocess.run(
        ["/bin/bash", str(RUNTIME)],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert time.monotonic() - started < 4
    assert result.returncode == 137
    assert "Vault is unhealthy" in result.stderr
    assert "terminating it so launchd can restart it" in result.stderr


def test_runtime_preserves_child_exit_status(tmp_path: Path) -> None:
    env = runtime_env(
        tmp_path,
        """\
        #!/usr/bin/env bash
        sleep 0.2
        exit 23
        """,
        curl_exit=0,
    )

    started = time.monotonic()
    result = subprocess.run(
        ["/bin/bash", str(RUNTIME)],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert time.monotonic() - started < 2
    assert result.returncode == 23
    assert "health monitor stopped unexpectedly" not in result.stderr


def test_start_force_restarts_loaded_service(tmp_path: Path) -> None:
    home = tmp_path / "home"
    plist = home / "Library" / "LaunchAgents" / "com.vault966.server.plist"
    plist.parent.mkdir(parents=True)
    plist.touch()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "launchctl-calls"
    write_executable(
        bin_dir / "launchctl",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {calls!s}
        if [[ "$1" == "print" ]]; then
          exit 0
        fi
        """,
    )
    write_executable(
        bin_dir / "curl",
        """\
        #!/usr/bin/env bash
        exit 0
        """,
    )

    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}"})
    result = subprocess.run(
        ["/bin/bash", str(SERVICE), "start"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "kickstart -k gui/" in calls.read_text()


def test_start_retries_transient_bootstrap_failure(tmp_path: Path) -> None:
    home = tmp_path / "home"
    plist = home / "Library" / "LaunchAgents" / "com.vault966.server.plist"
    plist.parent.mkdir(parents=True)
    plist.touch()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "launchctl-calls"
    loaded = tmp_path / "loaded-targets"
    attempts = tmp_path / "bootstrap-attempts"
    write_executable(
        bin_dir / "launchctl",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {calls!s}
        case "$1" in
          print)
            grep -qx "$2" {loaded!s} 2>/dev/null
            ;;
          bootstrap)
            label="$(basename "$3" .plist)"
            if [[ "$label" == "com.vault966.server" ]]; then
              count="$(cat {attempts!s} 2>/dev/null || echo 0)"
              count=$((count + 1))
              printf '%s' "$count" > {attempts!s}
              if [[ "$count" -eq 1 ]]; then
                echo "Bootstrap failed: transient launchd state" >&2
                exit 5
              fi
            fi
            printf '%s/%s\n' "$2" "$label" >> {loaded!s}
            ;;
          bootout)
            touch {loaded!s}
            grep -vx "$2" {loaded!s} > {loaded!s}.next || true
            mv {loaded!s}.next {loaded!s}
            ;;
        esac
        """,
    )
    write_executable(
        bin_dir / "curl",
        """\
        #!/usr/bin/env bash
        exit 0
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PATH": f"{bin_dir}:{env['PATH']}",
            "LAUNCHCTL_BOOTSTRAP_DELAY": "0",
        }
    )
    result = subprocess.run(
        ["/bin/bash", str(SERVICE), "start"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert attempts.read_text() == "2"
    assert "bootout gui/" in calls.read_text()


def test_restart_cleans_stale_deploy_artifacts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "scripts").mkdir()
    shutil.copy2(SERVICE, project / "scripts" / "vault_service.sh")
    for script_name in (
        "vault_runtime.sh",
        "vault_watchdog.sh",
        "sqlite_maintenance.py",
    ):
        (project / "scripts" / script_name).write_text("", encoding="utf-8")
    (project / "requirements.txt").write_text("", encoding="utf-8")
    (project / "vault.db").write_text("seed database\n", encoding="utf-8")
    (project / ".git").write_text("gitdir: /tmp/worktree\n", encoding="utf-8")

    home = tmp_path / "home"
    support = home / "Library" / "Application Support" / "Vault966"
    app = support / "app"
    data = support / "data"
    venv_python = support / ".venv" / "bin" / "python"
    app.mkdir(parents=True)
    data.mkdir(parents=True)
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    venv_python.chmod(venv_python.stat().st_mode | stat.S_IXUSR)

    for stale_dir in (".codex", ".agents", "skills", "reports", "node_modules"):
        (app / stale_dir).mkdir()
        (app / stale_dir / "stale.txt").write_text("stale\n", encoding="utf-8")
    for stale_file in (
        ".git",
        "vault.db.bak",
        "vault.db.before-service-20260706.bak",
        "vault.db-journal",
        "movie 2.py",
    ):
        (app / stale_file).write_text("stale\n", encoding="utf-8")
    existing_database = data / "vault.db"
    existing_database.write_text("live database\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    events = tmp_path / "events"
    loaded = tmp_path / "loaded-targets"
    domain = f"gui/{os.getuid()}"
    loaded.write_text(
        "\n".join(
            (
                f"{domain}/com.vault966.server",
                f"{domain}/com.vault966.watchdog",
                f"{domain}/com.vault966.maintenance",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    rsync_calls = tmp_path / "rsync-calls"
    uv_calls = tmp_path / "uv-calls"
    write_executable(
        bin_dir / "rsync",
        f"""\
        #!/usr/bin/env bash
        printf 'rsync\n' >> {events!s}
        printf '%s\n' "$*" > {rsync_calls!s}
        src="${{@: -2:1}}"
        dst="${{@: -1}}"
        mkdir -p "$dst/scripts"
        cp "$src/requirements.txt" "$dst/requirements.txt"
        cp "$src/scripts/vault_runtime.sh" "$dst/scripts/vault_runtime.sh"
        cp "$src/scripts/vault_watchdog.sh" "$dst/scripts/vault_watchdog.sh"
        cp "$src/scripts/sqlite_maintenance.py" "$dst/scripts/sqlite_maintenance.py"
        """,
    )
    write_executable(
        bin_dir / "uv",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {uv_calls!s}
        exit 0
        """,
    )
    write_executable(
        bin_dir / "launchctl",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {events!s}
        case "$1" in
          print)
            grep -qx "$2" {loaded!s} 2>/dev/null
            ;;
          bootout)
            touch {loaded!s}
            grep -vx "$2" {loaded!s} > {loaded!s}.next || true
            mv {loaded!s}.next {loaded!s}
            ;;
          bootstrap)
            label="$(basename "$3" .plist)"
            printf '%s/%s\n' "$2" "$label" >> {loaded!s}
            ;;
        esac
        """,
    )
    for command in ("plutil", "curl"):
        write_executable(
            bin_dir / command,
            """\
            #!/usr/bin/env bash
            exit 0
            """,
        )

    env = os.environ.copy()
    env.update({"HOME": str(home), "PATH": f"{bin_dir}:{env['PATH']}"})
    result = subprocess.run(
        ["/bin/bash", str(project / "scripts" / "vault_service.sh"), "restart"],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    assert "--exclude .git " in rsync_calls.read_text()
    assert uv_calls.exists()
    event_lines = events.read_text(encoding="utf-8").splitlines()
    assert event_lines.index("rsync") > event_lines.index(f"bootout {domain}/com.vault966.server")
    for stale_path in (
        ".git",
        ".codex",
        ".agents",
        "skills",
        "reports",
        "node_modules",
        "vault.db.bak",
        "vault.db.before-service-20260706.bak",
        "vault.db-journal",
        "movie 2.py",
    ):
        assert not (app / stale_path).exists()
    assert app.joinpath("vault.db").is_symlink()
    assert app.joinpath("vault.db").resolve() == existing_database
    assert existing_database.read_text(encoding="utf-8") == "live database\n"


def test_watchdog_restarts_after_repeated_health_failures(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "launchctl-calls"
    attempts = tmp_path / "curl-attempts"
    write_executable(
        bin_dir / "curl",
        f"""\
        #!/usr/bin/env bash
        printf 'x' >> {attempts!s}
        exit 1
        """,
    )
    write_executable(
        bin_dir / "launchctl",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {calls!s}
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "DOMAIN": "gui/501",
            "HEALTH_ATTEMPTS": "3",
            "HEALTH_RETRY_DELAY": "0",
        }
    )
    result = subprocess.run(
        ["/bin/bash", str(WATCHDOG)],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert attempts.read_text() == "xxx"
    assert calls.read_text().strip() == "kickstart -k gui/501/com.vault966.server"
    assert "health unavailable after 3 attempts" in result.stderr


def test_watchdog_does_not_restart_healthy_service(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "launchctl-calls"
    write_executable(
        bin_dir / "curl",
        """\
        #!/usr/bin/env bash
        exit 0
        """,
    )
    write_executable(
        bin_dir / "launchctl",
        f"""\
        #!/usr/bin/env bash
        printf '%s\n' "$*" >> {calls!s}
        """,
    )

    env = os.environ.copy()
    env.update({"PATH": f"{bin_dir}:{env['PATH']}"})
    result = subprocess.run(
        ["/bin/bash", str(WATCHDOG)],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert not calls.exists()
