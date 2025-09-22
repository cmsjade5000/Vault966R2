import re

from fastapi.testclient import TestClient


def test_search_by_query(client: TestClient) -> None:
    response = client.get("/movies/search", params={"q": "matrix"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "The Matrix"


def test_search_by_filters(client: TestClient) -> None:
    params = {
        "year_min": 1980,
        "year_max": 1985,
        "runtime_max": 120,
        "genres": "Sci-Fi",
        "moods": "Moody",
    }
    response = client.get("/movies/search", params=params)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Blade Runner"


def test_search_pagination(client: TestClient) -> None:
    response = client.get("/movies/search", params={"page": 2, "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["total"] == 33
    titles = [item["title"] for item in payload["items"]]
    assert len(titles) == 10
    assert titles[0] == "Movie 09"


def test_search_sorting_runtime(client: TestClient) -> None:
    response = client.get(
        "/movies/search",
        params={"order_by": "runtime_asc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    titles = [item["title"] for item in payload["items"]]
    assert titles[:5] == [
        "Toy Story",
        "Movie 00",
        "Movie 01",
        "Movie 02",
        "Movie 03",
    ]


def test_search_facets_respect_filters(client: TestClient) -> None:
    response = client.get(
        "/movies/search",
        params={"moods": "Exciting"},
    )
    assert response.status_code == 200
    payload = response.json()
    facets = payload["facets"]
    assert payload["total"] == 1
    assert facets["moods"]["Exciting"] == 1
    assert facets["genres"]["Sci-Fi"] == 1
    assert facets["genres"]["Action"] == 1


def test_movies_grid_stats_summary(client: TestClient) -> None:
    response = client.get("/ui/movies")
    assert response.status_code == 200

    facts = dict(
        re.findall(
            r'<div class="fact-label">(.*?)</div>\s*<div class="fact-value">(.*?)</div>',
            response.text,
        )
    )

    assert facts["Total entries"] == "33"
    assert facts["Average year"] == "2001"
    assert facts["Top genre"] == "Library"
    assert facts["Top mood"] == "General"
