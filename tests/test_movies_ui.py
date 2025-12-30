from fastapi.testclient import TestClient

from api.services.ui.grid import FILTER_COOKIE_NAME


def test_movies_grid_persists_filters_via_cookie(client: TestClient) -> None:
    first = client.get(
        "/ui/movies",
        params={
            "genres": "Science Fiction",
            "order_by": "runtime_asc",
        },
    )
    assert first.status_code == 200
    assert client.cookies.get(FILTER_COOKIE_NAME) is not None

    second = client.get("/ui/movies")
    assert second.status_code == 200
    html = second.text
    assert 'id="genres-input" value="Science Fiction"' in html
    assert 'option value="runtime_asc" selected' in html
    assert "Blade Runner" in html
    assert "Toy Story" not in html


def test_movies_grid_filters_by_mood(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"moods": "Moody"})
    assert response.status_code == 200
    html = response.text
    assert "Blade Runner" in html
    assert "The Matrix" not in html


def test_flags_page_lists_flagged_movies(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post("/movies/1/flag", json={"reason": "Metadata cleanup"}, headers=admin_headers)
    assert resp.status_code == 200

    page = client.get("/ui/flags")
    assert page.status_code == 200
    html = page.text
    assert "Flags" in html
    assert "Metadata cleanup" in html
