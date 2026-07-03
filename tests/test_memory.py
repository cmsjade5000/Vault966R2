from fastapi.testclient import TestClient

from api.models.flic_memory import FlicMemory


def test_get_picks_does_not_update_memory(client: TestClient, db_session):
    resp = client.get("/movies/picks")
    assert resp.status_code == 200

    history_resp = client.get("/fliclists/history")
    assert history_resp.status_code == 200
    assert history_resp.json() == []
    assert db_session.query(FlicMemory).count() == 0


def test_pick_memory_requires_same_origin(client: TestClient, login_profile):
    resp = client.get("/movies/picks")
    assert resp.status_code == 200
    picked = resp.json()

    login_profile(1)
    missing_origin = client.post(f"/movies/picks/{picked['id']}/memory")
    assert missing_origin.status_code == 403

    blocked = client.post(
        f"/movies/picks/{picked['id']}/memory",
        headers={"Origin": "http://evil.test"},
    )
    assert blocked.status_code == 403

    allowed = client.post(
        f"/movies/picks/{picked['id']}/memory",
        headers={"Origin": "http://testserver"},
    )
    assert allowed.status_code == 204


def test_memory_capped(client: TestClient):
    for _ in range(12):
        resp = client.get("/movies/picks")
        assert resp.status_code == 200
        picked = resp.json()
        memory_resp = client.post(f"/movies/picks/{picked['id']}/memory")
        assert memory_resp.status_code == 204

    history_resp = client.get("/fliclists/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) <= 10
    ids = [entry["id"] for entry in history]
    assert ids == sorted(ids, reverse=True)
