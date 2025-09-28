from api.models.movie import Movie
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

    assert result["where_to_watch"] == "Netflix; Hulu; Vudu"
    # Timestamp should be populated with an ISO-8601 value
    assert result["tmdb_last_scraped"]
