import httpx
import pytest

from api.models.movie import Movie
from api.services import movie_lookup


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"status code {self.status_code}")


def _clear_lookup_caches() -> None:
    movie_lookup._tmdb_search_ids.cache_clear()
    movie_lookup._tmdb_movie_detail.cache_clear()
    movie_lookup._omdb_details.cache_clear()


@pytest.fixture(autouse=True)
def _reset_lookup_caches():
    _clear_lookup_caches()
    yield
    _clear_lookup_caches()


@pytest.fixture()
def movie_id(db_session):
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()
    return movie.id


def test_movies_lookup_candidates_success(client, movie_id, monkeypatch):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", "tmdb-key")
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", "omdb-key")

    def fake_get(url, params=None, timeout=None):
        if "search/movie" in url:
            return DummyResponse(
                {
                    "results": [
                        {
                            "id": 200,
                            "popularity": 75,
                            "release_date": "2019-05-01",
                        },
                        {
                            "id": 100,
                            "popularity": 150,
                            "release_date": "2020-01-15",
                        },
                    ]
                }
            )
        if url.endswith("/100"):
            return DummyResponse(
                {
                    "id": 100,
                    "title": "The Matrix",
                    "overview": "Base overview",
                    "runtime": 130,
                    "release_date": "1999-03-31",
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "genres": [{"name": "Action"}, {"name": "Sci-Fi"}],
                    "external_ids": {"imdb_id": "tt0133093"},
                }
            )
        if url.endswith("/200"):
            return DummyResponse(
                {
                    "id": 200,
                    "title": "Another Choice",
                    "overview": "Secondary overview",
                    "runtime": 95,
                    "release_date": "2018-11-11",
                    "poster_path": None,
                    "backdrop_path": None,
                    "genres": [{"name": "Drama"}],
                    "external_ids": {"imdb_id": "tt7654321"},
                }
            )
        if "omdbapi.com" in url:
            imdb_id = params.get("i")
            return DummyResponse(
                {
                    "Response": "True",
                    "Plot": f"OMDb plot {imdb_id}",
                    "Runtime": "142 min",
                    "Poster": f"https://images.example/{imdb_id}.jpg",
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(movie_lookup.httpx, "get", fake_get)

    response = client.get(f"/movies/{movie_id}/lookup")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    first = payload["items"][0]
    assert first["tmdb_id"] == 100  # highest popularity result should be first
    assert first["title"] == "The Matrix"
    assert first["runtime"] == 142  # OMDb runtime overrides TMDb
    assert first["poster_url"].endswith("tt0133093.jpg")
    assert first["synopsis"] == "OMDb plot tt0133093"
    assert first["genres"] == ["Action", "Sci-Fi"]


def test_movies_lookup_candidates_empty_results(client, movie_id, monkeypatch):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", "tmdb-key")
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", None)

    def fake_get(url, params=None, timeout=None):
        if "search/movie" in url:
            return DummyResponse({"results": []})
        raise AssertionError("Detail should not be fetched when search is empty")

    monkeypatch.setattr(movie_lookup.httpx, "get", fake_get)

    response = client.get(f"/movies/{movie_id}/lookup")
    assert response.status_code == 404
    assert response.json()["detail"] == "No TMDb results found"


def test_movies_lookup_candidates_missing_key(client, movie_id, monkeypatch):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", None)
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", None)

    response = client.get(f"/movies/{movie_id}/lookup")
    assert response.status_code == 503
