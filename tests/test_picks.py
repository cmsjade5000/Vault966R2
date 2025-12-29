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


def test_pick_rejects_inverted_year_range(client: TestClient) -> None:
    response = client.get(
        "/movies/picks",
        params={"year_min": 2020, "year_max": 2000},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "year_min cannot be greater than year_max"
