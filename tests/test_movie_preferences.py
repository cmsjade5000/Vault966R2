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


def test_preference_mutations_require_same_origin_when_auth_enabled(client, login_profile) -> None:
    login_profile(1)
    movie_id = _first_movie_id(client)

    mutation_cases = [
        ("post", f"/movies/{movie_id}/like"),
        ("delete", f"/movies/{movie_id}/like"),
        ("post", f"/movies/{movie_id}/watchlist"),
        ("delete", f"/movies/{movie_id}/watchlist"),
    ]

    for method, path in mutation_cases:
        response = getattr(client, method)(path)
        assert response.status_code == 403

        response = getattr(client, method)(path, headers={"Origin": "http://evil.test"})
        assert response.status_code == 403

        response = getattr(client, method)(path, headers={"Origin": "http://testserver"})
        assert response.status_code == 200


def test_profile_switch_requires_same_origin_when_auth_enabled(client, login_profile) -> None:
    login_profile(1)

    response = client.post("/api/profiles/active", json={"profile_id": 1})
    assert response.status_code == 403

    response = client.post(
        "/api/profiles/active",
        json={"profile_id": 1},
        headers={"Origin": "http://evil.test"},
    )
    assert response.status_code == 403

    response = client.post(
        "/api/profiles/active",
        json={"profile_id": 1},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_watchlist_uses_library_movie_cards(client) -> None:
    movie_id = _first_movie_id(client)
    response = client.post(f"/movies/{movie_id}/watchlist")
    assert response.status_code == 200

    page = client.get("/ui/watchlist")
    assert page.status_code == 200
    assert 'class="library-shell page-shell"' in page.text
    assert 'class="library-heading"' in page.text
    assert "<h1>Watchlist</h1>" in page.text
    assert "<strong data-watchlist-total>1</strong> saved" in page.text
    assert "<span data-watchlist-total-label>movie</span>" in page.text
    assert "Personal picks" not in page.text
    assert "Back to movies" not in page.text
    assert 'class="results-shell page-shell"' not in page.text
    assert 'class="library-grid"' in page.text
    assert 'class="library-card"' in page.text
    assert 'class="library-card__actions"' in page.text
    assert 'data-preference-type="like"' in page.text
    assert 'data-preference-type="watchlist"' in page.text
    assert 'class="card-preferences"' not in page.text
    assert 'class="preference-button' not in page.text
    assert "css/movies.css?v=" in page.text
    assert "js/movie_preferences.js?v=" in page.text
    assert "js/movies_page.js" not in page.text
