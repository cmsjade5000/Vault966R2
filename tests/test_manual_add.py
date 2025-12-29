import csv
from typing import Optional

from fastapi.testclient import TestClient

from api.db import get_db
from api.models.movie import Movie
from api.routers.ui.manual_add import ManualMovieCreate, ManualMovieMetadata
from api.services import manual_add


EXPECTED_ENRICHED_FIELDNAMES = [
    "title",
    "year",
    "imdb_id",
    "tmdb_id",
    "runtime_min",
    "plot",
    "poster_url",
    "backdrop_url",
    "genres",
    "moods",
    "keywords",
    "imdb_rating",
    "imdb_votes",
    "rt_score",
    "watch_region",
    "providers_stream",
    "providers_rent",
    "providers_buy",
    "tmdb_watch_url",
    "languages",
    "countries",
    "collection",
    "tmdb_last_scraped",
]


def _fetch_movie(client: TestClient, title: str) -> Optional[dict]:
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


def test_manual_add_creates_movie_with_vudu_tag(client: TestClient, admin_headers: dict[str, str]):
    payload = ManualMovieCreate(
        title="Inception",
        year=2010,
        metadata=ManualMovieMetadata(
            overview="Dream heist.",
            runtime=148,
            imdb_id="tt1375666",
            tmdb_id=27205,
            poster_url="https://example.com/poster.jpg",
            backdrop_url="https://example.com/backdrop.jpg",
            genres=["Science Fiction"],
            where_to_watch=["Amazon Prime"],
        ),
        vudu=True,
    )

    resp = client.post(
        "/ui/movies/manual-add",
        json=payload.model_dump(),
        headers=admin_headers,
    )
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


def test_manual_add_rejects_duplicate_imdb(client: TestClient, admin_headers: dict[str, str]):
    base_payload = ManualMovieCreate(
        title="Edge of Tomorrow",
        year=2014,
        metadata=ManualMovieMetadata(
            overview="Live. Die. Repeat.",
            runtime=113,
            imdb_id="tt1631867",
            tmdb_id=137113,
            genres=["Action"],
        ),
    )

    first = client.post(
        "/ui/movies/manual-add",
        json=base_payload.model_dump(),
        headers=admin_headers,
    )
    assert first.status_code == 201

    duplicate_title = base_payload.model_copy(update={"title": "Edge of Tomorrow Redux"})
    second = client.post(
        "/ui/movies/manual-add",
        json=duplicate_title.model_dump(),
        headers=admin_headers,
    )
    assert second.status_code == 409
    assert "IMDb ID" in second.json()["message"]


def test_append_movie_to_cleaned_csv_writes_header_for_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manual_add, "DATA_DIR", tmp_path)

    wrote_row = manual_add.append_movie_to_cleaned_csv("Solaris", 1972)
    assert wrote_row is True

    path = tmp_path / "cleaned_titles.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["title", "year"]
        rows = list(reader)
    assert rows == [{"title": "Solaris", "year": "1972"}]


def test_append_movie_to_cleaned_csv_adds_header_for_empty_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manual_add, "DATA_DIR", tmp_path)

    path = tmp_path / "cleaned_titles.csv"
    path.touch()
    assert path.exists()
    assert path.stat().st_size == 0

    wrote_row = manual_add.append_movie_to_cleaned_csv("Dune", 1984)
    assert wrote_row is True

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ["title", "year"]
        rows = list(reader)
    assert rows == [{"title": "Dune", "year": "1984"}]


def test_append_movie_to_enriched_csv_writes_header_for_new_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manual_add, "DATA_DIR", tmp_path)

    wrote_row = manual_add.append_movie_to_enriched_csv(
        "Arrival",
        2016,
        metadata={"imdb_id": "tt2543164", "tmdb_id": 329865},
        providers=["Hulu"],
    )
    assert wrote_row is True

    path = tmp_path / "enriched_movies.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == EXPECTED_ENRICHED_FIELDNAMES
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["title"] == "Arrival"
    assert rows[0]["imdb_id"] == "tt2543164"
    assert rows[0]["providers_stream"] == "Hulu"


def test_append_movie_to_enriched_csv_adds_header_for_empty_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manual_add, "DATA_DIR", tmp_path)

    path = tmp_path / "enriched_movies.csv"
    path.touch()
    assert path.exists()
    assert path.stat().st_size == 0

    wrote_row = manual_add.append_movie_to_enriched_csv("Ex Machina", 2014)
    assert wrote_row is True

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == EXPECTED_ENRICHED_FIELDNAMES
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["title"] == "Ex Machina"
    assert rows[0]["year"] == "2014"
    for field in EXPECTED_ENRICHED_FIELDNAMES:
        if field in {"title", "year"}:
            continue
        if field == "watch_region":
            assert rows[0][field] == "US"
            continue
        assert rows[0][field] == ""
