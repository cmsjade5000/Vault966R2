from fastapi.testclient import TestClient

from api.db import get_db
from api.models.movie import Movie
from api.services import movie_trailers


def _db_session(client: TestClient):
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_select_tmdb_trailer_prefers_official_youtube_trailer() -> None:
    payload = {
        "results": [
            {
                "site": "YouTube",
                "type": "Trailer",
                "key": "unofficial_123",
                "name": "Unofficial trailer",
                "official": False,
                "iso_639_1": "en",
                "iso_3166_1": "US",
            },
            {
                "site": "YouTube",
                "type": "Trailer",
                "key": "official_456",
                "name": "Official Trailer",
                "official": True,
                "iso_639_1": "en",
                "iso_3166_1": "US",
            },
            {
                "site": "Vimeo",
                "type": "Trailer",
                "key": "vimeo-key",
                "name": "Wrong site",
            },
        ]
    }

    trailer = movie_trailers.select_tmdb_trailer(payload)

    assert trailer is not None
    assert trailer.site == "youtube"
    assert trailer.key == "official_456"
    assert trailer.embed_url == "https://www.youtube-nocookie.com/embed/official_456"


def test_select_tmdb_trailer_rejects_non_youtube_and_bad_keys() -> None:
    payload = {
        "results": [
            {"site": "YouTube", "type": "Trailer", "key": "bad key"},
            {"site": "YouTube", "type": "Featurette", "key": "featurette_123"},
            {"site": "Vimeo", "type": "Trailer", "key": "vimeo_123"},
        ]
    }

    assert movie_trailers.select_tmdb_trailer(payload) is None


def test_movie_trailer_endpoint_fetches_and_caches_trailer(client: TestClient, monkeypatch) -> None:
    for db in _db_session(client):
        movie = Movie(title="Trailer Movie", tmdb_id=12345)
        db.add(movie)
        db.commit()
        movie_id = movie.id

    monkeypatch.setattr(
        movie_trailers,
        "_fetch_tmdb_videos",
        lambda tmdb_id: {
            "results": [
                {
                    "site": "YouTube",
                    "type": "Trailer",
                    "key": "trailer_789",
                    "name": "Main Trailer",
                    "official": True,
                    "iso_639_1": "en",
                    "iso_3166_1": "US",
                }
            ]
        },
    )

    response = client.get(f"/movies/{movie_id}/trailer")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site"] == "youtube"
    assert payload["key"] == "trailer_789"
    assert payload["embed_url"] == "https://www.youtube-nocookie.com/embed/trailer_789"

    for db in _db_session(client):
        movie = db.query(Movie).filter(Movie.id == movie_id).one()
        assert movie.trailer_site == "youtube"
        assert movie.trailer_key == "trailer_789"
        assert movie.trailer_checked_at is not None


def test_movie_trailer_endpoint_returns_404_without_trailer(
    client: TestClient, monkeypatch
) -> None:
    for db in _db_session(client):
        movie = Movie(title="No Trailer Movie", tmdb_id=12345)
        db.add(movie)
        db.commit()
        movie_id = movie.id

    monkeypatch.setattr(
        movie_trailers,
        "_fetch_tmdb_videos",
        lambda tmdb_id: {"results": []},
    )

    response = client.get(f"/movies/{movie_id}/trailer")

    assert response.status_code == 404
    assert response.json()["message"] == "Trailer not available"
