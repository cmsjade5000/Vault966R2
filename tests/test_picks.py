from fastapi.testclient import TestClient


def test_pick_with_mood(client: TestClient) -> None:
    response = client.get("/movies/picks", params={"mood": "Exciting"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "The Matrix"
    mood_names = [mood["name"] for mood in payload["moods"]]
    assert "High-energy" in mood_names


def test_pick_honors_full_genre_and_mood_filter_set(client: TestClient) -> None:
    response = client.get(
        "/movies/picks",
        params={
            "genres": "Sci-Fi, Action",
            "moods": "High-energy, Mind-bending",
            "year_min": 1990,
            "year_max": 2000,
            "runtime_min": 120,
            "runtime_max": 140,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "The Matrix"
    assert {genre["name"] for genre in payload["genres"]} >= {"Sci-Fi", "Action"}
    assert {mood["name"] for mood in payload["moods"]} >= {
        "High-energy",
        "Mind-bending",
    }


def test_pick_honors_search_with_multi_value_filters(client: TestClient) -> None:
    response = client.get(
        "/movies/picks",
        params={
            "q": "Matrix",
            "genres": "Sci-Fi, Action",
            "moods": "High-energy, Mind-bending",
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "The Matrix"


def test_pick_requires_every_selected_genre_and_mood(client: TestClient) -> None:
    response = client.get(
        "/movies/picks",
        params={
            "genres": "Sci-Fi, Animation",
            "moods": "High-energy, Family",
        },
    )

    assert response.status_code == 404


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
