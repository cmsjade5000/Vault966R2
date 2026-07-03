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
                    "release_date": "",
                    "release_dates": {
                        "results": [
                            {
                                "iso_3166_1": "US",
                                "release_dates": [
                                    {
                                        "release_date": "1999-04-01T00:00:00.000Z",
                                        "certification": "R",
                                    }
                                ],
                            }
                        ]
                    },
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "genres": [{"name": "Action"}, {"name": "Sci-Fi"}],
                    "external_ids": {"imdb_id": "tt0133093"},
                    "keywords": {"keywords": [{"name": "simulation"}, {"name": "hacker"}]},
                    "watch/providers": {
                        "results": {
                            "US": {
                                "flatrate": [{"provider_name": "HBO Max"}],
                                "rent": [{"provider_name": "Apple TV"}],
                                "buy": [{"provider_name": "Amazon Video"}],
                            }
                        }
                    },
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
                    "images": {
                        "posters": [{"file_path": "/fallback-poster.jpg"}],
                        "backdrops": [{"file_path": "/fallback-backdrop.jpg"}],
                    },
                    "genres": [{"name": "Drama"}],
                    "external_ids": {},
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
                    "Rated": "R",
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(movie_lookup.httpx, "get", fake_get)

    response = client.post(f"/movies/{movie_id}/lookup")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    first = payload["items"][0]
    assert first["tmdb_id"] == 100  # highest popularity result should be first
    assert first["title"] == "The Matrix"
    assert first["runtime"] == 142  # OMDb runtime overrides TMDb
    assert first["poster_url"].endswith("tt0133093.jpg")
    assert first["synopsis"] == "OMDb plot tt0133093"
    assert first["genres"] == ["Action", "Science Fiction"]
    assert first["release_date"] == "1999-04-01"
    assert first["keywords"] == ["simulation", "hacker"]
    assert first["certificate"] == "R"
    assert first["where_to_watch"] == [
        "HBO Max",
        "Apple TV (rent)",
        "Amazon Video (buy)",
    ]

    second = payload["items"][1]
    assert second["poster_url"] == "https://image.tmdb.org/t/p/w342/fallback-poster.jpg"


def test_movies_lookup_candidates_empty_results(client, movie_id, monkeypatch):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", "tmdb-key")
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", None)

    def fake_get(url, params=None, timeout=None):
        if "search/movie" in url:
            return DummyResponse({"results": []})
        raise AssertionError("Detail should not be fetched when search is empty")

    monkeypatch.setattr(movie_lookup.httpx, "get", fake_get)

    response = client.post(f"/movies/{movie_id}/lookup")
    assert response.status_code == 404
    assert response.json()["message"] == "No TMDb results found"


def test_movies_lookup_candidates_missing_key(client, movie_id, monkeypatch, db_session):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", None)
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", None)

    db_session.add(Movie(title="Blade Runner Final Cut", year=1982, runtime=116))
    db_session.commit()

    response = client.post(f"/movies/{movie_id}/lookup")
    assert response.status_code == 200
    payload = response.json()
    assert "notice" in payload
    assert payload["items"]
    assert any(item["source"] == "vault" for item in payload["items"])


def test_movies_lookup_get_uses_local_candidates_only(client, movie_id, monkeypatch, db_session):
    monkeypatch.setattr(movie_lookup.settings, "tmdb_api_key", "tmdb-key")
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", "omdb-key")

    def fail_provider(*args, **kwargs):
        raise AssertionError("GET lookup must not call external providers")

    monkeypatch.setattr(movie_lookup, "lookup_movie_candidates", fail_provider)
    monkeypatch.setattr(movie_lookup.httpx, "get", fail_provider)
    db_session.add(Movie(title="Blade Runner Final Cut", year=1982, runtime=116))
    db_session.commit()

    response = client.get(f"/movies/{movie_id}/lookup")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["notice"].startswith("External lookup requires a same-origin POST")


def test_movies_lookup_provider_post_requires_same_origin(
    client, movie_id, monkeypatch, login_profile
):
    monkeypatch.setattr(
        "api.routers.movies.lookup_movie_candidates",
        lambda title, year, limit=5: [{"title": title, "source": "tmdb"}],
    )
    login_profile(1)

    missing_origin = client.post(f"/movies/{movie_id}/lookup")
    response = client.post(
        f"/movies/{movie_id}/lookup",
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Blade Runner"
    assert response.json()["items"][0]["source"] == "tmdb"


def test_movies_lookup_provider_post_is_throttled(client, movie_id, monkeypatch, login_profile):
    monkeypatch.setattr(
        "api.routers.movies.lookup_movie_candidates",
        lambda title, year, limit=5: [{"title": title, "source": "tmdb"}],
    )
    login_profile(1)
    headers = {"Origin": "http://testserver"}

    responses = [client.post(f"/movies/{movie_id}/lookup", headers=headers) for _ in range(11)]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429
