from api.config import settings


def test_health_is_public_and_omits_database_details(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_name": settings.app_name}


def test_security_headers_allow_only_youtube_nocookie_frames(client):
    response = client.get("/health")

    csp = response.headers["Content-Security-Policy"]
    assert "frame-src https://www.youtube-nocookie.com;" in csp
