"""Probe Vault's real ASGI app with disposable SQLite and synthetic auth."""

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

import httpx
import pytest


@pytest.mark.parametrize("invalid_telemetry", [False, True])
def test_actual_app_lifespan_auth_and_telemetry(tmp_path, invalid_telemetry):
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(root),
        "DATABASE_URL": f"sqlite:///{tmp_path / 'synthetic.db'}",
        "DISABLE_AUTH": "false",
        "LOGIN_ACCESS_KEY": "synthetic-vault-probe",
        "LOGIN_PASSCODE": "synthetic-passcode",
        "LOGIN_SESSION_SECRET": "synthetic-session-secret-for-dependency-test",
    }
    if invalid_telemetry:
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "invalid-synthetic-endpoint"
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--lifespan",
                "on",
            ],
            cwd=tmp_path,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
                for _ in range(200):
                    assert process.poll() is None, "Synthetic Vault process exited during startup"
                    try:
                        if client.get("/readyz").status_code == 200:
                            break
                    except httpx.TransportError:
                        time.sleep(0.05)
                else:
                    pytest.fail("Synthetic Vault did not become ready")
                login = client.get("/login")
                assert login.status_code == 200
                assert "Content-Security-Policy" in login.headers
                assert "X-Request-ID" in login.headers
                blocked = client.get("/ui/movies")
                assert blocked.status_code == 302
                assert blocked.headers["location"] == "/login"
                unlocked = client.post(
                    "/login",
                    data={
                        "access_key": env["LOGIN_ACCESS_KEY"],
                        "passcode": env["LOGIN_PASSCODE"],
                    },
                    headers={"Accept": "application/json"},
                )
                assert unlocked.status_code == 200
                selected = client.post(
                    "/login",
                    data={"profile_id": "1"},
                    headers={"Accept": "application/json"},
                )
                assert selected.status_code == 200
                assert client.get("/ui/movies").status_code == 200
                assert "/readyz" in client.get("/openapi.json").json()["paths"]
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("Synthetic Vault did not shut down gracefully")
        assert process.returncode in (0, -signal.SIGTERM)
        log.seek(0)
        output = log.read()
        assert "Application startup complete" in output
        assert "Application shutdown complete" in output
        if invalid_telemetry:
            assert "automatic telemetry configuration failed" in output
