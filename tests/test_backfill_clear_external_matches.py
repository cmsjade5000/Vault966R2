import httpx
from types import SimpleNamespace

from scripts.backfill_clear_external_matches import (
    _clear_missing_id_flag,
    exact_title_year,
    omdb_by_title,
    release_year,
    unique_exact_tmdb_match,
)


def test_release_year_accepts_omdb_ranges() -> None:
    assert release_year("2019") == 2019
    assert release_year("2019–2020") == 2019
    assert release_year("") is None


def test_exact_title_year_requires_both_fields() -> None:
    assert exact_title_year("The Addams Family (2019)", 2019, "The Addams Family", "2019")
    assert exact_title_year("Her (2013)", 2013, "Her", "2013-12-18")
    assert not exact_title_year("Footloose", 1984, "Footloose", "2011-10-14")
    assert not exact_title_year("The Gift", 2015, "The Gifted", "2015")


def test_provider_searches_use_normalized_title() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/3/search/movie":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "title": "The Boss",
                            "release_date": "2016-04-08",
                        }
                    ]
                },
            )
        if request.url.path == "/3/movie/1":
            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "title": "The Boss",
                    "release_date": "2016-04-08",
                },
            )
        return httpx.Response(
            200,
            json={
                "Response": "True",
                "Title": "The Boss",
                "Year": "2016",
                "imdbID": "tt2702724",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert unique_exact_tmdb_match(client, "tmdb-key", "The Boss (Unrated)", 2016)
        assert omdb_by_title(client, "omdb-key", "The Boss (Unrated)", 2016)

    assert requests[0].url.params["query"] == "the boss"
    assert requests[2].url.params["t"] == "the boss"


def test_clear_flag_removes_resolved_id_and_year_notes() -> None:
    deleted = []
    flag = SimpleNamespace(
        reason="Human review",
        notes="Year is missing; No source IDs",
    )
    movie = SimpleNamespace(flag=flag, year=2015)
    session = SimpleNamespace(delete=deleted.append)

    _clear_missing_id_flag(session, movie)

    assert deleted == [flag]
