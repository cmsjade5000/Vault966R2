from fastapi.testclient import TestClient


def test_picks_updates_memory(client: TestClient):
    resp = client.get("/movies/picks")
    assert resp.status_code == 200
    picked = resp.json()

    history_resp = client.get("/fliclists/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) >= 1
    assert history[0]["movie_id"] == picked["id"]


def test_memory_capped(client: TestClient):
    for _ in range(12):
        resp = client.get("/movies/picks")
        assert resp.status_code == 200

    history_resp = client.get("/fliclists/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) <= 10
    ids = [entry["id"] for entry in history]
    assert ids == sorted(ids, reverse=True)
