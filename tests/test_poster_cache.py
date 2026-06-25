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


def test_cached_movie_poster_downloads_once(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    db_session.commit()

    calls: list[str] = []

    def fake_download(source_url, cache_dir, stem):
        calls.append(source_url)
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = cache_dir / f"{stem}.jpg"
        path.write_bytes(b"poster-bytes")
        return path

    monkeypatch.setattr(posters, "POSTER_CACHE_DIR", tmp_path)
    monkeypatch.setattr(posters, "download_poster", fake_download)

    first = client.get(f"/ui/posters/{movie.id}/w185")
    second = client.get(f"/ui/posters/{movie.id}/w185")

    assert first.status_code == 200
    assert first.content == b"poster-bytes"
    assert first.headers["content-type"] == "image/jpeg"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert "immutable" in first.headers["cache-control"]
    assert second.status_code == 200
    assert calls == ["https://image.tmdb.org/t/p/w185/example.jpg"]


def test_cached_movie_poster_returns_502_for_failed_upstream(
    client,
    db_session,
    tmp_path,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.poster_url = "https://image.tmdb.org/t/p/w500/example.jpg"
    db_session.commit()

    def fail_download(*_args):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(posters, "POSTER_CACHE_DIR", tmp_path)
    monkeypatch.setattr(posters, "download_poster", fail_download)

    response = client.get(f"/ui/posters/{movie.id}/w185")

    assert response.status_code == 502
    assert response.json()["message"] == "Poster temporarily unavailable"


def test_background_cache_failure_is_isolated(monkeypatch) -> None:
    def fail_cache(_movie_id):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(poster_cache, "cache_movie_posters", fail_cache)

    poster_cache.cache_movie_posters_safely(42)
