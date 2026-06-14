from api.services import movie_lookup
from api.services.movie_lookup import _enrich_with_omdb, lookup_omdb_candidates


def test_enrich_with_omdb_parses_ratings_votes_and_rt_score():
    candidate = {}
    omdb_payload = {
        "Response": "True",
        "Plot": "A plot.",
        "Poster": "https://example.com/poster.jpg",
        "Runtime": "123 min",
        "imdbRating": "7.4",
        "imdbVotes": "12,345",
        "Ratings": [
            {"Source": "Internet Movie Database", "Value": "7.4/10"},
            {"Source": "Rotten Tomatoes", "Value": "91%"},
        ],
    }

    _enrich_with_omdb(candidate, omdb_payload)

    assert candidate["runtime"] == 123
    assert candidate["imdb_rating"] == 7.4
    assert candidate["imdb_votes"] == 12345
    assert candidate["rt_score"] == 91


def test_lookup_omdb_candidates_returns_manual_search_options(monkeypatch):
    monkeypatch.setattr(movie_lookup.settings, "omdb_api_key", "omdb-key")

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "Response": "True",
                "Search": [
                    {
                        "Title": "Cinderella",
                        "Year": "2015",
                        "imdbID": "tt1661199",
                    }
                ],
            }

    monkeypatch.setattr(movie_lookup.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        movie_lookup,
        "_omdb_details",
        lambda api_key, imdb_id: {
            "Response": "True",
            "Title": "Cinderella",
            "Year": "2015",
            "Runtime": "105 min",
            "Plot": "A manual OMDb result.",
            "Poster": "https://images.example/cinderella.jpg",
            "Genre": "Adventure, Family, Fantasy",
            "Rated": "PG",
            "imdbID": imdb_id,
            "imdbRating": "6.9",
            "imdbVotes": "190,000",
        },
    )

    candidates = lookup_omdb_candidates("Cinderella (2015)", 2015)

    assert len(candidates) == 1
    assert candidates[0]["source"] == "omdb"
    assert candidates[0]["imdb_id"] == "tt1661199"
    assert candidates[0]["runtime"] == 105
