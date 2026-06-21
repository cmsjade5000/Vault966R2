from fastapi.testclient import TestClient

from api.config import settings


def test_delete_movie_removes_detail(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.delete("/movies/1", headers=admin_headers)
    assert resp.status_code == 204

    detail = client.get("/movies/1/detail")
    assert detail.status_code == 404


def test_delete_movie_allows_admin_profile_session(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    client.post("/login", data={"profile_id": "1"}, follow_redirects=False)

    missing_origin = client.delete("/movies/1")
    resp = client.delete("/movies/1", headers={"Origin": "http://testserver"})

    assert missing_origin.status_code == 403
    assert resp.status_code == 204
