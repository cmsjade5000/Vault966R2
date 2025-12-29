from scripts.backfill_posters import normalize_title, select_poster_candidate


def test_select_poster_candidate_prefers_exact_title_and_year() -> None:
    requested_title = "Footloose"
    requested_year = 1984
    candidates = [
        {
            "poster_url": "https://images.example/2011.jpg",
            "match_confidence": 0.82,
            "matched_tmdb_title": "Footloose (2011)",
            "matched_tmdb_year": 2011,
            "tmdb_id": 2,
        },
        {
            "poster_url": "https://images.example/1984.jpg",
            "match_confidence": 0.82,
            "matched_tmdb_title": "Footloose",
            "matched_tmdb_year": 1984,
            "tmdb_id": 1,
        },
    ]

    selected = select_poster_candidate(requested_title, requested_year, candidates, 0.7)
    assert selected is not None
    assert selected["tmdb_id"] == 1


def test_select_poster_candidate_requires_poster_and_confidence() -> None:
    requested_title = "The Thing"
    requested_year = 1982
    candidates = [
        {
            "poster_url": "",
            "match_confidence": 0.95,
            "matched_tmdb_title": "The Thing",
            "matched_tmdb_year": 1982,
            "tmdb_id": 1,
        },
        {
            "poster_url": "https://images.example/thing.jpg",
            "match_confidence": 0.6,
            "matched_tmdb_title": "The Thing",
            "matched_tmdb_year": 1982,
            "tmdb_id": 2,
        },
    ]

    selected = select_poster_candidate(requested_title, requested_year, candidates, 0.7)
    assert selected is None


def test_normalize_title_handles_ampersand() -> None:
    assert normalize_title("Fish & Chips") == normalize_title("Fish and   Chips")
