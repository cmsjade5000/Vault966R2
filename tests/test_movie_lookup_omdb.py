from api.services.movie_lookup import _enrich_with_omdb


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
