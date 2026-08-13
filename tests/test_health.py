from sqlalchemy.exc import OperationalError

from api.config import settings
from api.db import get_db
from api.schemas.common import ErrorResponse
from api.schemas.health import LivenessResponse, ReadinessResponse


def test_health_is_public_and_omits_database_details(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_name": settings.app_name}


def test_liveness_is_public_and_does_not_depend_on_database(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    original_override = client.app.dependency_overrides[get_db]

    def unavailable_database():
        raise AssertionError("liveness must not access the database")

    client.app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/livez", follow_redirects=False)
    finally:
        client.app.dependency_overrides[get_db] = original_override

    assert response.status_code == 200
    assert LivenessResponse.model_validate(response.json()) == LivenessResponse(status="alive")
    assert "location" not in response.headers


def test_readiness_is_public_and_succeeds_when_database_responds(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    response = client.get("/readyz", follow_redirects=False)

    assert response.status_code == 200
    assert ReadinessResponse.model_validate(response.json()) == ReadinessResponse(status="ready")
    assert "location" not in response.headers


def test_readiness_returns_503_when_database_check_fails(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    original_override = client.app.dependency_overrides[get_db]

    class UnavailableSession:
        def execute(self, _statement):
            raise OperationalError("SELECT 1", {}, RuntimeError("database unavailable"))

    def unavailable_database():
        yield UnavailableSession()

    client.app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/readyz", follow_redirects=False)
    finally:
        client.app.dependency_overrides[get_db] = original_override

    assert response.status_code == 503
    error = ErrorResponse.model_validate(response.json())
    assert error.error_code == "http_error"
    assert error.message == "Database readiness check failed."
    assert error.request_id == response.headers["X-Request-ID"]
    assert "location" not in response.headers


def test_probe_openapi_contracts_are_typed(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert paths["/livez"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LivenessResponse"
    }
    assert paths["/readyz"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ReadinessResponse"
    }
    assert paths["/readyz"]["get"]["responses"]["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }


def test_api_docs_are_intentionally_public_with_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)

    for path in ("/docs", "/redoc", "/openapi.json"):
        response = client.get(path, follow_redirects=False)

        assert response.status_code == 200

    openapi = client.get("/openapi.json").json()
    assert openapi["info"]["title"] == settings.app_name


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
    monkeypatch.setattr(settings, "login_access_key", None)
    monkeypatch.setattr(settings, "login_passcode", None)
    monkeypatch.setattr(settings, "login_access_key_user_a", None)
    monkeypatch.setattr(settings, "login_passcode_user_a", None)
    monkeypatch.setattr(settings, "login_access_key_user_b", None)
    monkeypatch.setattr(settings, "login_passcode_user_b", None)

    response = client.get("/ui/movies", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/setup"
    assert response.headers["Content-Security-Policy"].startswith("default-src 'self';")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
