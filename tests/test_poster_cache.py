from __future__ import annotations

import httpx

from api.models.movie import Movie
from api.routers.ui import posters
from api.services import poster_cache


def test_poster_source_url_accepts_only_tmdb_images() -> None:
    assert (
        poster_cache.poster_source_url(
            "https://media.themoviedb.org/t/p/original/example.jpg?language=en",
            "w185",
        )
        == "https://image.tmdb.org/t/p/w185/example.jpg?language=en"
    )
    assert (
        poster_cache.poster_source_url(
            "https://m.media-amazon.com/images/M/poster._V1_SX300.jpg",
            "w342",
        )
        == "https://m.media-amazon.com/images/M/poster._V1_SX300.jpg"
    )

    for value in (
        "http://image.tmdb.org/t/p/w500/example.jpg",
        "https://example.com/t/p/w500/example.jpg",
        "https://image.tmdb.org/not-a-poster.jpg",
    ):
        try:
            poster_cache.poster_source_url(value, "w185")
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected poster source rejection: {value}")


def test_cached_movie_poster_serves_cached_file(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    db_session.commit()

    source_url = poster_cache.poster_source_url(movie.poster_url, "w185")
    stem = poster_cache.cache_stem(movie.id, "w185", source_url)
    (tmp_path / f"{stem}.jpg").write_bytes(b"poster-bytes")

    monkeypatch.setattr(posters, "POSTER_CACHE_DIR", tmp_path)

    first = client.get(f"/ui/posters/{movie.id}/w185")
    second = client.get(f"/ui/posters/{movie.id}/w185")

    assert first.status_code == 200
    assert first.content == b"poster-bytes"
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in first.headers["cache-control"]
    assert second.status_code == 200


def test_cached_movie_poster_cache_miss_does_not_download(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    db_session.commit()

    monkeypatch.setattr(posters, "POSTER_CACHE_DIR", tmp_path)

    response = client.get(f"/ui/posters/{movie.id}/w185")

    assert response.status_code == 404
    assert response.json()["message"] == "Poster cache miss"
    assert not list(tmp_path.iterdir())


def test_background_cache_downloads_missing_poster(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    db_session.commit()

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, source_url):
            return httpx.Response(
                200,
                request=httpx.Request("GET", source_url),
                headers={"content-type": "image/jpeg"},
                content=f"poster:{source_url}".encode("utf-8"),
            )

    class TestSessionFactory:
        def __enter__(self):
            return db_session

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(poster_cache, "SessionLocal", TestSessionFactory)
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: FakeClient())

    downloaded, cached = poster_cache.cache_movie_posters(
        movie.id,
        sizes=("w185",),
        cache_dir=tmp_path,
    )

    assert (downloaded, cached) == (1, 0)
    source_url = poster_cache.poster_source_url(movie.poster_url, "w185")
    stem = poster_cache.cache_stem(movie.id, "w185", source_url)
    assert (tmp_path / f"{stem}.jpg").read_bytes() == f"poster:{source_url}".encode("utf-8")


def test_background_cache_failure_is_isolated(monkeypatch) -> None:
    def fail_cache(_movie_id):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(poster_cache, "cache_movie_posters", fail_cache)

    poster_cache.cache_movie_posters_safely(42)
