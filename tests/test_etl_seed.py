import pathlib
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_ROOT / "tests"
if str(TESTS_DIR) in sys.path:
    sys.path.remove(str(TESTS_DIR))
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))
sys.modules.pop("legacy", None)

from api.models.movie import Movie

try:
    from scripts import etl_seed  # type: ignore
except RuntimeError:
    from legacy.etl import etl_seed as etl_seed  # type: ignore


@pytest.fixture()
def in_memory_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    etl_seed.Base.metadata.create_all(bind=engine)

    original_session_local = etl_seed.SessionLocal
    monkeypatch.setattr(etl_seed, "SessionLocal", TestingSessionLocal)

    yield TestingSessionLocal

    etl_seed.Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(etl_seed, "SessionLocal", original_session_local)


def test_parse_list_deduplicates_and_handles_delimiters():
    result = etl_seed.split_multi("Action; Drama; Action")
    assert result == ["Action", "Drama"]

    result = etl_seed.split_multi(["Mystery", "mystery", "Thriller"])
    assert result == ["Mystery", "Thriller"]


def test_normalize_row_requires_title():
    with pytest.raises(etl_seed.MalformedRowError):
        etl_seed.normalize_row({}, 1)


def test_normalize_row_with_extended_columns():
    raw = {
        "title": "Interstellar",
        "release_year": "2014",
        "runtime_min": "169",
        "plot_summary": "Space epic",
        "imdb_id": "tt0816692",
        "tmdb_id": "157336",
        "genre": "Sci-Fi; Adventure",
        "poster_url": "https://example.com/interstellar.jpg",
    }

    record = etl_seed.normalize_row(raw, 4)
    assert record["title"] == "Interstellar"
    assert record["year"] == 2014
    assert record["runtime"] == 169
    assert record["plot"] == "Space epic"
    assert record["genres"] == ["Sci-Fi", "Adventure"]
    assert record["moods"] == []


def test_load_rows_csv(tmp_path):
    sample_csv = pathlib.Path("legacy/etl/samples/more_movies.csv")
    rows = etl_seed.load_rows(sample_csv, "csv", "utf-8")
    assert len(rows) == 3
    assert rows[0]["title"] == "The Shawshank Redemption"


def test_load_rows_csv_skips_preface_line():
    sample_csv = pathlib.Path("legacy/etl/samples/vault966_titles_years.csv")
    rows = etl_seed.load_rows(sample_csv, "csv", "utf-8")

    assert len(rows) > 900
    assert rows[0]["title"] == "Abduction"
    assert rows[0]["year"] == "2011"
    assert None not in rows[0]
    assert "Table 1" not in rows[0]


def test_process_record_insert_and_update(in_memory_session):
    record = {
        "title": "Inception",
        "year": 2010,
        "runtime": 148,
        "plot": "A thief steals corporate secrets through dream-sharing technology.",
        "imdb_id": "tt1375666",
        "tmdb_id": 27205,
        "poster_url": "https://example.com/inception.jpg",
        "backdrop_url": None,
        "genres": ["Sci-Fi", "Thriller"],
        "moods": ["Mind-bending"],
    }

    action, reason = etl_seed.process_record(
        record,
        dry_run=False,
        duplicates_path=pathlib.Path("reports/duplicates.csv"),
    )
    assert action == "inserted"
    assert reason is None

    with in_memory_session() as session:
        movie = session.execute(select(Movie).where(Movie.imdb_id == "tt1375666")).scalar_one()
        assert movie.title == "Inception"
        assert {genre.name for genre in movie.genres} == {"Sci-Fi", "Thriller"}

    record_update = {
        **record,
        "runtime": 150,
        "genres": ["Sci-Fi"],
        "moods": ["Thoughtful"],
    }
    action, reason = etl_seed.process_record(
        record_update,
        dry_run=False,
        duplicates_path=pathlib.Path("reports/duplicates.csv"),
    )
    assert action == "updated"
    assert reason is None

    with in_memory_session() as session:
        movie = session.execute(select(Movie).where(Movie.imdb_id == "tt1375666")).scalar_one()
        assert movie.runtime == 150
        assert {genre.name for genre in movie.genres} == {"Sci-Fi"}
        assert {mood.name for mood in movie.moods} == {"Thoughtful"}


def test_process_record_dry_run_does_not_commit(in_memory_session):
    record = {
        "title": "Blade Runner 2049",
        "year": 2017,
        "runtime": 164,
        "plot": "A young blade runner discovers a long-buried secret.",
        "imdb_id": "tt1856101",
        "tmdb_id": 335984,
        "poster_url": None,
        "backdrop_url": None,
        "genres": ["Sci-Fi"],
        "moods": ["Atmospheric"],
    }

    action, reason = etl_seed.process_record(
        record,
        dry_run=True,
        duplicates_path=pathlib.Path("reports/duplicates.csv"),
    )
    assert action == "inserted"
    assert reason is None

    with in_memory_session() as session:
        result = session.execute(
            select(Movie).where(Movie.imdb_id == "tt1856101")
        ).scalar_one_or_none()
        assert result is None


def test_process_record_skips_no_changes(in_memory_session):
    record = {
        "title": "Moonlight",
        "year": 2016,
        "runtime": 111,
        "plot": "A young man deals with his dysfunctional home life.",
        "imdb_id": "tt4975722",
        "tmdb_id": 376867,
        "poster_url": None,
        "backdrop_url": None,
        "genres": ["Drama"],
        "moods": ["Intimate"],
    }

    action, _ = etl_seed.process_record(
        record,
        dry_run=False,
        duplicates_path=pathlib.Path("reports/duplicates.csv"),
    )
    assert action == "inserted"

    action, reason = etl_seed.process_record(
        record,
        dry_run=False,
        duplicates_path=pathlib.Path("reports/duplicates.csv"),
    )
    assert action == "skipped"
    assert reason == "duplicate_db"


def test_coerce_int_handles_messy_values():
    assert etl_seed.coerce_int("1999") == 1999
    assert etl_seed.coerce_int(" 110 ") == 110
    assert etl_seed.coerce_int("1999.0") == 1999
    assert etl_seed.coerce_int("NaN") is None
    assert etl_seed.coerce_int("unknown") is None
    assert etl_seed.coerce_int(2001) == 2001
    assert etl_seed.coerce_int(2001.0) == 2001


def test_normalize_providers_handles_mapping_payload():
    payload = {
        "US": {
            "flatrate": [
                {"provider_name": "Netflix", "logo_path": "/path/netflix.png"},
                {"provider_name": "Hulu", "provider_id": 15},
            ],
            "link": "https://example.com",
        }
    }

    normalized = etl_seed.normalize_providers(payload)
    assert normalized == "Netflix; Hulu"


def test_merge_where_to_watch_merges_string_and_mapping():
    existing = "Netflix"
    incoming = {
        "US": {
            "flatrate": [
                {"provider_name": "Hulu"},
                {"provider_name": "Netflix"},
            ]
        }
    }

    merged = etl_seed.merge_where_to_watch(existing, incoming)
    assert merged == "Netflix; Hulu"


def test_normalize_imdb_id_variants():
    assert etl_seed.normalize_imdb_id("tt1234567") == "tt1234567"
    assert etl_seed.normalize_imdb_id("  TT7654321  ") == "tt7654321"
    assert etl_seed.normalize_imdb_id("12345678") == "tt12345678"
    assert etl_seed.normalize_imdb_id("tt0066999") == "tt0066999"
    assert etl_seed.normalize_imdb_id("123456789") == "tt123456789"
    assert etl_seed.normalize_imdb_id("tt0066999") == "tt0066999"
    assert etl_seed.normalize_imdb_id("abc123") is None
    assert etl_seed.normalize_imdb_id("tt1234") is None


def test_sanitize_title_for_search_strips_parentheticals():
    assert etl_seed.sanitize_title_for_search("Dirty Harry (Unrated)") == "dirty harry"
    assert etl_seed.sanitize_title_for_search("Alien (1979) (Director's Cut)") == "alien"


def test_resolve_imdb_via_network_tmdb_handles_parenthetical_titles(monkeypatch):
    record = {"title": "Alien (1979)", "year": 1979}
    calls = []

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params})
        if "search/movie" in url:
            assert params["query"] == "alien"
            return DummyResponse(
                {
                    "results": [
                        {
                            "title": "Alien",
                            "id": 42,
                            "release_date": "1979-05-25",
                        }
                    ]
                }
            )
        if url.endswith("/movie/42/external_ids"):
            return DummyResponse({"imdb_id": "tt1234567"})
        pytest.fail(f"Unexpected URL {url}")

    monkeypatch.setattr(etl_seed.httpx, "get", fake_get)

    imdb_id, tag, tmdb_id = etl_seed.resolve_imdb_via_network(
        record,
        allow_network=True,
        tmdb_key="tmdb-key",
        omdb_key=None,
        max_retries=2,
        retry_delay=0.2,
    )

    assert imdb_id == "tt1234567"
    assert tag == "tmdb"
    assert tmdb_id == 42
    assert calls[0]["params"]["query"] == "alien"


def test_resolve_imdb_via_network_omdb_strips_parenthetical_titles(monkeypatch):
    record = {"title": "Dirty Harry (Unrated)", "year": 1971}
    calls = []

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params})
        if "search/movie" in url:
            return DummyResponse({"results": []})
        if "omdbapi.com" in url:
            assert params["t"].lower() == "dirty harry"
            if "y" in params:
                assert params["y"] == 1971
            return DummyResponse({"Response": "True", "imdbID": "tt0066999"})
        pytest.fail(f"Unexpected URL {url}")

    monkeypatch.setattr(etl_seed.httpx, "get", fake_get)

    imdb_id, tag, tmdb_id = etl_seed.resolve_imdb_via_network(
        record,
        allow_network=True,
        tmdb_key="tmdb-key",
        omdb_key="omdb-key",
        max_retries=2,
        retry_delay=0.2,
    )

    assert imdb_id == "tt0066999"
    assert tag == "omdb_title_year"
    assert tmdb_id is None
    assert calls[1]["params"]["t"].lower() == "dirty harry"


def test_resolve_imdb_via_network_allows_year_plus_minus_one(monkeypatch):
    record = {"title": "Dirty Harry", "year": 1971}

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append({"url": url, "params": params})
        if "search/movie" in url:
            return DummyResponse({"results": []})
        if "omdbapi.com" in url:
            if params.get("y") == 1972:
                return DummyResponse({"Response": "True", "imdbID": "tt0066999", "Year": "1972"})
            return DummyResponse({"Response": "False", "Error": "Movie not found!"})
        pytest.fail(f"Unexpected URL {url}")

    monkeypatch.setattr(etl_seed.httpx, "get", fake_get)

    imdb_id, tag, tmdb_id = etl_seed.resolve_imdb_via_network(
        record,
        allow_network=True,
        tmdb_key="tmdb-key",
        omdb_key="omdb-key",
        max_retries=2,
        retry_delay=0.2,
    )

    assert imdb_id == "tt0066999"
    assert tag == "omdb_title_year_plus1"
    assert tmdb_id is None


def test_resolve_imdb_via_network_records_last_omdb_payload(monkeypatch):
    record = {"title": "Dirty Harry", "year": 1971}

    class DummyResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        if "search/movie" in url:
            return DummyResponse({"results": []})
        if "omdbapi.com" in url:
            return DummyResponse({"Response": "False", "Error": "Movie not found!"})
        pytest.fail(f"Unexpected URL {url}")

    monkeypatch.setattr(etl_seed.httpx, "get", fake_get)

    imdb_id, tag, tmdb_id = etl_seed.resolve_imdb_via_network(
        record,
        allow_network=True,
        tmdb_key="tmdb-key",
        omdb_key="omdb-key",
        max_retries=2,
        retry_delay=0.2,
    )

    assert imdb_id is None
    assert tag == "lookup_failed"
    assert tmdb_id is None
    assert etl_seed.resolver_state.last_omdb_payload == {
        "Response": "False",
        "Error": "Movie not found!",
    }


def test_pick_imdb_id_prefers_tmdb():
    tmdb_payload = {"imdb_id": "tt0066999"}
    omdb_payload = {"Response": "True", "imdbID": "tt1234567"}
    assert etl_seed.pick_imdb_id(tmdb_payload, omdb_payload) == "tt0066999"


def test_pick_imdb_id_falls_back_to_omdb():
    tmdb_payload = {"imdb_id": None}
    omdb_payload = {"Response": "True", "imdbID": "tt1234567"}
    assert etl_seed.pick_imdb_id(tmdb_payload, omdb_payload) == "tt1234567"


def test_pick_imdb_id_handles_missing_values():
    assert etl_seed.pick_imdb_id(None, None) is None
    assert etl_seed.pick_imdb_id({}, {"Response": "False"}) is None
