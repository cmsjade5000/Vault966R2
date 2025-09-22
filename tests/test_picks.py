from fastapi.testclient import TestClient


def test_pick_with_mood(client: TestClient) -> None:
    response = client.get("/movies/picks", params={"mood": "Exciting"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "The Matrix"
    mood_names = [mood["name"] for mood in payload["moods"]]
    assert "Exciting" in mood_names


def test_pick_mood_not_found(client: TestClient) -> None:
    response = client.get("/movies/picks", params={"mood": "Nonexistent"})
    assert response.status_code == 404
