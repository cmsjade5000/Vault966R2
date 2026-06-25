import os
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


def test_runtime_forces_unresponsive_child_to_exit(tmp_path: Path) -> None:
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
    assert "forcing termination" in result.stderr


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
