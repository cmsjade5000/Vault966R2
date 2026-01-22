def _first_movie_id(client) -> int:
    response = client.get("/movies")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    return payload[0]["id"]


def test_like_watchlist_is_profile_scoped(client) -> None:
    movie_id = _first_movie_id(client)

    response = client.post(f"/movies/{movie_id}/like")
    assert response.status_code == 200
    payload = response.json()
    assert payload["liked"] is True
    assert payload["watchlist"] is False

    profiles = client.get("/api/profiles").json()["profiles"]
    other_profile = profiles[1]["id"]
    response = client.post(
        "/api/profiles/active",
        json={"profile_id": other_profile},
    )
    assert response.status_code == 200

    response = client.post(f"/movies/{movie_id}/watchlist")
    assert response.status_code == 200
    payload = response.json()
    assert payload["liked"] is False
    assert payload["watchlist"] is True

    response = client.post(f"/movies/{movie_id}/like")
    assert response.status_code == 200
    payload = response.json()
    assert payload["liked"] is True
    assert payload["watchlist"] is True

    response = client.delete(f"/movies/{movie_id}/watchlist")
    assert response.status_code == 200
    payload = response.json()
    assert payload["watchlist"] is False
