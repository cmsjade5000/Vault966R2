import logging

import httpx

from api.models.movie import Movie
from legacy.etl import enrich_tmdb
from legacy.etl.enrich_tmdb import build_row


def test_build_row_handles_json_where_to_watch():
    movie = Movie(title="Example Movie")
    movie.where_to_watch = {
        "US": {
            "flatrate": [
                {"provider_name": "Netflix"},
                {"provider_name": "Hulu"},
            ],
            "rent": [
                {"provider_name": "Vudu"},
            ],
        }
    }

    result = build_row(
        movie,
        payload=None,
        poster_size="w500",
        backdrop_size="w780",
        provider_region="US",
    )

    assert result["watch_region"] == "US"
    assert result["providers_stream"] == "Netflix; Hulu"
    assert result["providers_rent"] == "Vudu"
    # Timestamp should be populated with an ISO-8601 value
    assert result["tmdb_last_scraped"]


def test_tmdb_transport_log_redacts_query_provider_secret(caplog) -> None:
    sentinel = "SENTINEL_LEGACY_ENRICH_SECRET"

    class FailingClient:
        def get(self, url, *, params):
            request = httpx.Request(
                "GET",
                f"https://api.themoviedb.org/3{url}",
                params=params,
            )
            raise httpx.ConnectError(f"connection failed for {request.url}", request=request)

    caplog.set_level(logging.WARNING)

    payload = enrich_tmdb.fetch_tmdb_payload(FailingClient(), sentinel, 42)

    assert payload is None
    message = caplog.messages[-1]
    assert sentinel not in message
    assert "[REDACTED]" in message
    assert "connection failed" in message
    assert "append_to_response=keywords" in message
