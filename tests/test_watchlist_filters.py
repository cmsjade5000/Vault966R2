from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from api.models.movie import Movie
from api.models.profile import MoviePreference


class WatchlistPage(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.movie_ids: list[int] = []
        self.detail_links: list[str] = []
        self.elements: dict[str, dict[str, str | None]] = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "data-movie-card" in attributes:
            self.movie_ids.append(int(attributes["data-movie-id"]))
        if tag == "a" and "data-movie-detail-link" in attributes:
            self.detail_links.append(attributes["href"])
        for name in (
            "data-watchlist-view",
            "data-watchlist-empty",
            "data-watchlist-no-results",
            "data-watchlist-grid",
        ):
            if name in attributes:
                self.elements[name] = attributes


@pytest.fixture()
def saved_movies(client, db_session):
    profile_id = client.get("/api/profiles").json()["active_profile_id"]
    titles_and_runtimes = [
        ("After Rain", 99),
        ("after rain", 100),
        ("After Sunset", 119),
        ("After Midnight", 120),
        ("After Unknown", None),
        ("After Zero", 0),
        ("Elsewhere", 80),
        ("100% Fun_Club", 95),
        ("100 Percent Fun Club", 90),
    ]
    movies = [
        Movie(title=title, runtime=runtime, plot="After is present only in this plot")
        for title, runtime in titles_and_runtimes
    ]
    db_session.add_all(movies)
    db_session.flush()
    db_session.add_all(
        MoviePreference(profile_id=profile_id, movie_id=movie.id, watchlist=True)
        for movie in movies
    )
    db_session.commit()
    return {movie.title: movie.id for movie in movies}


def test_watchlist_orders_saved_movies_by_title_with_stable_case_ties(client, saved_movies):
    page = client.get("/ui/watchlist")
    assert page.status_code == 200
    parsed = WatchlistPage(page.text)
    expected_titles = sorted(saved_movies, key=lambda title: (title.lower(), title))
    assert parsed.movie_ids == [saved_movies[title] for title in expected_titles]
    assert "<strong data-watchlist-total>9</strong> saved" in page.text
    assert "<strong data-watchlist-results>9</strong>" in page.text
    assert parsed.elements["data-watchlist-view"]["data-watchlist-saved-total"] == "9"
    assert parsed.elements["data-watchlist-view"]["data-watchlist-filtered"] == "false"


@pytest.mark.parametrize(
    ("runtime", "expected_titles"),
    [
        ("under100", ["After Rain", "Elsewhere", "100% Fun_Club", "100 Percent Fun Club"]),
        (
            "under120",
            [
                "After Rain",
                "after rain",
                "After Sunset",
                "Elsewhere",
                "100% Fun_Club",
                "100 Percent Fun Club",
            ],
        ),
    ],
)
def test_watchlist_runtime_limits_are_strict_and_exclude_unknown_runtime(
    client, saved_movies, runtime, expected_titles
):
    page = client.get("/ui/watchlist", params={"runtime": runtime})
    assert page.status_code == 200
    parsed = WatchlistPage(page.text)
    assert set(parsed.movie_ids) == {saved_movies[title] for title in expected_titles}
    assert "<strong data-watchlist-total>9</strong> saved" in page.text
    assert f"<strong data-watchlist-results>{len(expected_titles)}</strong>" in page.text
    assert f'<option value="{runtime}" selected>' in page.text
    assert "Under 100 means less than 100 minutes" in page.text
    assert 'href="/ui/watchlist">Clear filters</a>' in page.text


@pytest.mark.parametrize(
    ("query", "runtime", "expected_titles"),
    [
        (
            " AFTER ",
            "any",
            [
                "After Rain",
                "after rain",
                "After Sunset",
                "After Midnight",
                "After Unknown",
                "After Zero",
            ],
        ),
        ("after", "under100", ["After Rain"]),
        ("after", "under120", ["After Rain", "after rain", "After Sunset"]),
        ("100%", "any", ["100% Fun_Club"]),
        ("Fun_", "any", ["100% Fun_Club"]),
    ],
)
def test_watchlist_title_search_combines_with_runtime_and_escapes_wildcards(
    client, saved_movies, query, runtime, expected_titles
):
    page = client.get("/ui/watchlist", params={"q": query, "runtime": runtime})
    assert page.status_code == 200
    parsed = WatchlistPage(page.text)
    assert set(parsed.movie_ids) == {saved_movies[title] for title in expected_titles}
    assert "<strong data-watchlist-total>9</strong> saved" in page.text
    assert f"<strong data-watchlist-results>{len(expected_titles)}</strong>" in page.text


def test_watchlist_distinguishes_no_saved_movies_from_no_filter_matches(client, saved_movies):
    filtered = client.get("/ui/watchlist?q=does-not-exist&runtime=under100")
    parsed = WatchlistPage(filtered.text)
    assert parsed.movie_ids == []
    assert "hidden" in parsed.elements["data-watchlist-empty"]
    assert "hidden" not in parsed.elements["data-watchlist-no-results"]
    assert "hidden" in parsed.elements["data-watchlist-grid"]
    assert "<strong data-watchlist-total>9</strong> saved" in filtered.text
    assert "<strong data-watchlist-results>0</strong>" in filtered.text
    assert "No saved movies match these filters." in filtered.text

    profiles = client.get("/api/profiles").json()["profiles"]
    switched = client.post("/api/profiles/active", json={"profile_id": profiles[1]["id"]})
    assert switched.status_code == 200
    empty = client.get("/ui/watchlist?q=After&runtime=under100")
    parsed = WatchlistPage(empty.text)
    assert parsed.movie_ids == []
    assert "hidden" not in parsed.elements["data-watchlist-empty"]
    assert "hidden" in parsed.elements["data-watchlist-no-results"]
    assert parsed.elements["data-watchlist-view"]["data-watchlist-saved-total"] == "0"


def test_watchlist_filters_preserve_detail_return_context_and_do_not_change_preferences(
    client, db_session, saved_movies
):
    preferences_before = [
        (pref.profile_id, pref.movie_id, pref.liked, pref.watchlist)
        for pref in db_session.query(MoviePreference).order_by(MoviePreference.id).all()
    ]
    page = client.get("/ui/watchlist", params={"q": "After", "runtime": "under100"})
    parsed = WatchlistPage(page.text)
    assert parsed.movie_ids == [saved_movies["After Rain"]]
    return_to = parse_qs(urlsplit(parsed.detail_links[0]).query)["return_to"][0]
    assert return_to == "/ui/watchlist?q=After&runtime=under100"
    detail = client.get(parsed.detail_links[0])
    assert detail.status_code == 200
    assert 'href="/ui/watchlist?q=After&amp;runtime=under100"' in detail.text
    assert "← Back to Watchlist" in detail.text
    preferences_after = [
        (pref.profile_id, pref.movie_id, pref.liked, pref.watchlist)
        for pref in db_session.query(MoviePreference).order_by(MoviePreference.id).all()
    ]
    assert preferences_after == preferences_before


def test_watchlist_filter_inputs_are_bounded_and_html_escaped(client, saved_movies):
    assert client.get("/ui/watchlist", params={"q": "x" * 121}).status_code == 422
    for runtime in ("", "under90", "120", "under100|under120"):
        assert client.get("/ui/watchlist", params={"runtime": runtime}).status_code == 422
    page = client.get("/ui/watchlist", params={"q": '<script>"&'})
    assert page.status_code == 200
    assert '<script>"&' not in page.text
    assert "&lt;script&gt;&#34;&amp;" in page.text


def test_watchlist_search_does_not_expose_other_profiles_saved_movies(client, db_session):
    profiles = client.get("/api/profiles").json()["profiles"]
    other_movie = Movie(title="Other profile secret pick", runtime=90)
    db_session.add(other_movie)
    db_session.flush()
    db_session.add(
        MoviePreference(profile_id=profiles[1]["id"], movie_id=other_movie.id, watchlist=True)
    )
    db_session.commit()
    page = client.get("/ui/watchlist?q=secret&runtime=under100")
    assert page.status_code == 200
    assert WatchlistPage(page.text).movie_ids == []
    assert "Other profile secret pick" not in page.text
    assert "<strong data-watchlist-total>0</strong> saved" in page.text
