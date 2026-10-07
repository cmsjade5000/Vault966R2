"""Exercise Uvicorn over a real socket, without starting the Vault service."""

import socket
import signal
import subprocess
import sys
import time

import httpx
import pytest


@pytest.fixture(params=[False, True], ids=["direct", "trusted-loopback"])
def uvicorn_probe(tmp_path, request):
    (tmp_path / "probe.py").write_text(
        """async def app(scope, receive, send):
    if scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.accept"})
        while True:
            event = await receive()
            if event["type"] == "websocket.disconnect":
                return
            if event["type"] == "websocket.receive":
                await send({"type": "websocket.send", "text": event["text"]})
    else:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": scope["client"][0].encode()})
"""
    )
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "probe:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--lifespan",
        "off",
        "--timeout-keep-alive",
        "1",
    ]
    args += (
        ["--proxy-headers", "--forwarded-allow-ips=127.0.0.1"]
        if request.param
        else ["--no-proxy-headers"]
    )
    with (tmp_path / "server.log").open("w+") as log:
        process = subprocess.Popen(args, cwd=tmp_path, stdout=log, stderr=log)
        try:
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                if process.poll() is not None:
                    log.seek(0)
                    pytest.fail(log.read())
                try:
                    if httpx.get(url, timeout=0.2, trust_env=False).status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.05)
            else:
                pytest.fail("Uvicorn did not become ready")
            yield url, port, request.param
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                pytest.fail("Uvicorn did not shut down gracefully")
        assert process.returncode in (0, -signal.SIGTERM)
        log.seek(0)
        assert "Finished server process" in log.read()


def test_connection_close_and_proxy_trust(uvicorn_probe):
    url, port, trusted = uvicorn_probe
    response = httpx.get(url, trust_env=False, headers={"X-Forwarded-For": "198.51.100.7"})
    assert response.text == ("198.51.100.7" if trusted else "127.0.0.1")
    with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
        client.sendall(
            b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive, ClOsE\r\n\r\n"
        )
        chunks = []
        while chunk := client.recv(4096):
            chunks.append(chunk)
        assert b"200 OK" in b"".join(chunks)
        assert b"connection: close" in b"".join(chunks).lower()


def test_websocket_survives_http_keepalive(uvicorn_probe):
    from websockets.sync.client import connect

    url, _, _ = uvicorn_probe
    with connect(url.replace("http://", "ws://"), proxy=None) as client:
        time.sleep(1.5)
        client.send("still connected")
        assert client.recv(timeout=3) == "still connected"
