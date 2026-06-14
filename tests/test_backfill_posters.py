import httpx

from scripts.backfill_posters import (
    fetch_tmdb_page_match,
    fetch_tmdb_page_poster,
    normalize_title,
    select_poster_candidate,
    valid_tmdb_poster_url,
)


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
    assert normalize_title("The Boss (Unrated)") == normalize_title("The Boss")
    assert normalize_title("Her (2013)") == normalize_title("Her")
    assert normalize_title("The Last House (Unrated) [2009]") == normalize_title(
        "The Last House"
    )
    assert normalize_title("American Psycho (Uncut Version)") == normalize_title(
        "American Psycho"
    )


def test_valid_tmdb_poster_url_restricts_host_and_image_path() -> None:
    assert (
        valid_tmdb_poster_url(
            "https://media.themoviedb.org/t/p/w500/aOIuZAjPaRIE6CMzbazvcHuHXDc.jpg"
        )
        is not None
    )
    assert valid_tmdb_poster_url("https://example.com/t/p/w500/poster.jpg") is None
    assert valid_tmdb_poster_url("javascript:alert(1)") is None


def test_fetch_tmdb_page_poster_uses_first_valid_open_graph_image() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/movie/603"
        return httpx.Response(
            200,
            text=(
                '<meta property="og:title" content="The Matrix">'
                '<meta property="og:image" content="https://example.com/bad.jpg">'
                '<meta property="og:image" '
                'content="https://media.themoviedb.org/t/p/w500/poster.jpg">'
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_tmdb_page_poster(client, 603) == (
            "https://media.themoviedb.org/t/p/w500/poster.jpg"
        )


def test_fetch_tmdb_page_match_returns_title_and_poster() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                '<meta property="og:title" content="The Matrix">'
                '<meta property="og:image" '
                'content="https://media.themoviedb.org/t/p/w500/poster.jpg">'
            ),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_tmdb_page_match(client, 603) == {
            "title": "The Matrix",
            "poster_url": "https://media.themoviedb.org/t/p/w500/poster.jpg",
        }
