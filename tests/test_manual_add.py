from fastapi.testclient import TestClient

from api.db import get_db
from api.models.movie import Movie


def _fetch_movie(client: TestClient, title: str) -> dict | None:
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        movie = db.query(Movie).filter(Movie.title == title).one_or_none()
        if movie is None:
            return None
        return {
            "title": movie.title,
            "year": movie.year,
            "imdb_id": movie.imdb_id,
            "tmdb_id": movie.tmdb_id,
            "where_to_watch": movie.where_to_watch,
        }
    finally:
        generator.close()


def test_manual_add_creates_movie_with_vudu_tag(client: TestClient):
    payload = {
        "title": "Inception",
        "year": 2010,
        "metadata": {
            "overview": "Dream heist.",
            "runtime": 148,
            "imdb_id": "tt1375666",
            "tmdb_id": 27205,
            "poster_url": "https://example.com/poster.jpg",
            "backdrop_url": "https://example.com/backdrop.jpg",
            "genres": ["Science Fiction"],
            "where_to_watch": ["Amazon Prime"],
        },
        "vudu": True,
    }

    resp = client.post("/ui/movies/manual-add", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Inception"
    assert body["imdb_id"] == "tt1375666"
    assert set(body["where_to_watch"]) == {"Amazon Prime", "Vudu"}

    db_movie = _fetch_movie(client, "Inception")
    assert db_movie is not None
    assert db_movie["imdb_id"] == "tt1375666"
    assert db_movie["tmdb_id"] == 27205
    assert "Vudu" in (db_movie["where_to_watch"] or "")


def test_manual_add_rejects_duplicate_imdb(client: TestClient):
    base_payload = {
        "title": "Edge of Tomorrow",
        "year": 2014,
        "metadata": {
            "overview": "Live. Die. Repeat.",
            "runtime": 113,
            "imdb_id": "tt1631867",
            "tmdb_id": 137113,
            "genres": ["Action"],
        },
    }

    first = client.post("/ui/movies/manual-add", json=base_payload)
    assert first.status_code == 201

    second = client.post("/ui/movies/manual-add", json=base_payload)
    assert second.status_code == 409
    assert "IMDb ID" in second.json()["detail"]
