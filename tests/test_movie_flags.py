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
