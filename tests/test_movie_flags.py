from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def test_flag_and_unflag_movie(client: TestClient) -> None:
    payload = {"reason": "Missing poster", "notes": "Need Blu-ray scan"}
    response = client.post("/movies/1/flag", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["movie_id"] == 1
    assert body["reason"] == "Missing poster"

    flags_response = client.get("/movies/flags")
    assert flags_response.status_code == 200
    flags = flags_response.json()
    assert any(flag["movie_id"] == 1 for flag in flags)

    search = client.get("/movies/search")
    search_body = search.json()
    flagged_titles = [item for item in search_body["items"] if item["flagged"]]
    assert any(movie["id"] == 1 for movie in flagged_titles)

    clear_response = client.delete("/movies/1/flag")
    assert clear_response.status_code == 204

    flags_after = client.get("/movies/flags").json()
    assert all(flag["movie_id"] != 1 for flag in flags_after)


def test_update_movie_metadata_resolves_flag(client: TestClient) -> None:
    client.post("/movies/1/flag", json={"reason": "Needs runtime"})

    payload = {
        "runtime": 123,
        "plot": "Updated plot",
        "poster_url": "",
        "where_to_watch": ["Blu-ray"],
        "genres": ["Science Fiction", "Adventure"],
        "resolve_flag": True,
    }
    response = client.patch("/movies/1", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["runtime"] == 123
    assert body["flagged"] is False
    assert body["where_to_watch"] == "Blu-ray"

    detail = client.get("/movies/1/detail").json()
    assert detail["flagged"] is False


def test_update_movie_metadata_handles_optional_fields(client: TestClient) -> None:
    payload = {
        "awards": "Won 2 Oscars",
        "imdb_id": "tt0083658",
        "tmdb_id": 78,
        "imdb_rating": 8.1,
        "imdb_votes": 1234567,
        "metascore": 90,
        "tomato_meter": 89,
        "tomato_audience": 91,
        "rt_score": 95,
        "poster_url": " https://example.com/poster.jpg ",
        "backdrop_url": "https://example.com/backdrop.jpg",
        "where_to_watch": ["Netflix", "Vudu", "Netflix"],
        "languages": "English, Japanese",
        "countries": "United States",
        "collection": "Blade Runner Collection",
        "last_tmdb_fetch_at": datetime(2024, 1, 1, 12, tzinfo=timezone.utc).isoformat(),
        "last_omdb_fetch_at": datetime(2024, 1, 2, 12, tzinfo=timezone.utc).isoformat(),
        "tmdb_etag": "etag-value",
        "tmdb_payload_sha": "sha-tmdb",
        "omdb_payload_sha": "sha-omdb",
    }

    response = client.patch("/movies/1", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["awards"] == "Won 2 Oscars"
    assert body["imdb_id"] == "tt0083658"
    assert body["tmdb_id"] == 78
    assert body["imdb_rating"] == 8.1
    assert body["imdb_votes"] == 1234567
    assert body["metascore"] == 90
    assert body["tomato_meter"] == 89
    assert body["tomato_audience"] == 91
    assert body["poster_url"] == "https://example.com/poster.jpg"
    assert body["backdrop_url"] == "https://example.com/backdrop.jpg"
    assert body["where_to_watch"] == "Netflix; Vudu"
    assert body["languages"] == "English, Japanese"
    assert body["countries"] == "United States"
    assert body["collection"] == "Blade Runner Collection"
    assert body["last_tmdb_fetch_at"].startswith("2024-01-01T12:00:00")
    assert body["last_omdb_fetch_at"].startswith("2024-01-02T12:00:00")
    assert body["tmdb_etag"] == "etag-value"
    assert body["tmdb_payload_sha"] == "sha-tmdb"
    assert body["omdb_payload_sha"] == "sha-omdb"

    detail = client.get("/movies/1/detail").json()
    assert detail["rt_score"] == 95


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"year": 1700}, "Year must be between 1888 and 2100"),
        ({"runtime": -5}, "Runtime cannot be negative"),
        ({"imdb_rating": 11}, "IMDb rating must be between 0 and 10"),
        ({"imdb_votes": -10}, "IMDb votes cannot be negative"),
        ({"metascore": 101}, "Metascore must be between 0 and 100"),
        ({"tomato_meter": 150}, "Tomatometer score must be between 0 and 100"),
        ({"tomato_audience": -3}, "Audience score must be between 0 and 100"),
        ({"rt_score": 101}, "Rotten Tomatoes score must be between 0 and 100"),
        ({"tmdb_id": -1}, "TMDB id cannot be negative"),
    ],
)
def test_update_movie_rejects_invalid_values(
    client: TestClient, payload: dict[str, object], message: str
) -> None:
    response = client.patch("/movies/1", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == message


def test_resolve_flag_without_other_changes(client: TestClient) -> None:
    client.post("/movies/1/flag", json={"reason": "Needs review"})

    response = client.patch("/movies/1", json={"resolve_flag": True})
    assert response.status_code == 200
    body = response.json()
    assert body["flagged"] is False
    assert body["runtime"] == 117
