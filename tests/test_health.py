from api.config import settings


def test_health_is_public_and_omits_database_details(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_name": settings.app_name}


def test_security_headers_allow_only_youtube_nocookie_frames(client):
    response = client.get("/health")

    csp = response.headers["Content-Security-Policy"]
    assert "frame-src https://www.youtube-nocookie.com;" in csp


def test_security_headers_apply_to_unauthenticated_api_rejects(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)

    response = client.get("/movies/")

    assert response.status_code == 401
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_security_headers_apply_to_unauthenticated_ui_redirects(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)

    response = client.get("/ui/movies", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
