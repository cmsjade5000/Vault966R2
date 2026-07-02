from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.models.movie import Genre, Mood, Movie


def test_search_by_query(client: TestClient) -> None:
    response = client.get("/movies/search", params={"q": "matrix"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "The Matrix"


def test_search_query_with_literal_wildcards(client: TestClient, db_session: Session) -> None:
    library_genre = db_session.query(Genre).filter_by(name="Library").one()
    general_mood = db_session.query(Mood).filter_by(name="General").one()

    movie = Movie(
        title="Discount 100%",
        year=2024,
        runtime=95,
        imdb_id="ttdiscount100",
        tmdb_id=99999,
        genres=[library_genre],
        moods=[general_mood],
    )
    db_session.add(movie)
    db_session.commit()

    response = client.get("/movies/search", params={"q": "%"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Discount 100%"


def test_search_query_with_literal_underscore(client: TestClient, db_session: Session) -> None:
    library_genre = db_session.query(Genre).filter_by(name="Library").one()
    general_mood = db_session.query(Mood).filter_by(name="General").one()

    movie = Movie(
        title="Mission_Control",
        year=2023,
        runtime=102,
        imdb_id="ttmissioncontrol",
        tmdb_id=99998,
        genres=[library_genre],
        moods=[general_mood],
    )
    db_session.add(movie)
    db_session.commit()

    response = client.get("/movies/search", params={"q": "_"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "Mission_Control"


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


def test_search_sorting_runtime_keeps_unknown_runtimes_last(
    client: TestClient, db_session: Session
) -> None:
    library_genre = db_session.query(Genre).filter_by(name="Library").one()
    general_mood = db_session.query(Mood).filter_by(name="General").one()

    movie = Movie(
        title="Runtime Unknown",
        year=2024,
        runtime=None,
        imdb_id="ttruntimeunknown",
        tmdb_id=99997,
        genres=[library_genre],
        moods=[general_mood],
    )
    db_session.add(movie)
    db_session.commit()

    response = client.get(
        "/movies/search",
        params={"order_by": "runtime_asc", "page_size": 100},
    )

    assert response.status_code == 200
    titles = [item["title"] for item in response.json()["items"]]
    assert titles[-1] == "Runtime Unknown"


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


def test_search_rejects_inverted_year_range(client: TestClient) -> None:
    response = client.get(
        "/movies/search",
        params={"year_min": 2020, "year_max": 2000},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "year_min cannot be greater than year_max"


def test_search_rejects_inverted_runtime_range(client: TestClient) -> None:
    response = client.get(
        "/movies/search",
        params={"runtime_min": 150, "runtime_max": 90},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "runtime_min cannot be greater than runtime_max"


def test_search_genre_synonyms(client: TestClient) -> None:
    response = client.get(
        "/movies/search",
        params={"genres": "Science Fiction"},
    )
    assert response.status_code == 200
    payload = response.json()
    titles = {item["title"] for item in payload["items"]}
    assert {"Blade Runner", "The Matrix"}.issubset(titles)
