from datetime import date

from api.models.usage_event import UsageEvent
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.profile import MoviePreference, Profile
from api.routers.ui.discover import (
    RAIL_DEFINITIONS,
    _build_discover_rails,
    _ordered_rail_definitions,
    _pick_selected_for_you,
    _rail_candidates,
    _stable_daily_rank,
)
from api.services.ui.templates import poster_image_url
from api.services.trusted_movies import get_untrusted_movie_ids, trusted_movie_query
from core.genres import split_and_normalize


def test_genre_normalizer_treats_a_string_as_one_value() -> None:
    assert split_and_normalize("Drama, Horror") == ["Drama, Horror"]
    assert split_and_normalize("Drama / Horror") == ["Drama", "Horror"]


def test_library_grid_and_list_render_the_same_page(client) -> None:
    params = {"preset": "under-100", "page": 1}
    grid = client.get("/ui/movies", params={**params, "view": "grid"})
    list_view = client.get("/ui/movies", params={**params, "view": "list"})

    assert grid.status_code == 200
    assert list_view.status_code == 200
    for movie_id in range(1, 34):
        assert (f'data-movie-id="{movie_id}"' in grid.text) == (
            f'data-movie-id="{movie_id}"' in list_view.text
        )


def test_usage_events_accept_only_whitelisted_fields(client, db_session) -> None:
    accepted = client.post(
        "/ui/events",
        json={
            "event_name": "view_changed",
            "page": "library",
            "context": "list",
        },
    )
    assert accepted.status_code == 204
    assert db_session.query(UsageEvent).count() == 1

    unknown = client.post(
        "/ui/events",
        json={
            "event_name": "raw_search_recorded",
            "page": "library",
            "context": "private words",
            "search_text": "do not store this",
        },
    )
    assert unknown.status_code == 422
    assert db_session.query(UsageEvent).count() == 1


def test_personalized_impression_event_uses_fixed_whitelisted_context(client, db_session) -> None:
    response = client.post(
        "/ui/events",
        json={
            "event_name": "personalized_recommendations_shown",
            "page": "discover",
            "context": "selected_for_you",
        },
    )

    assert response.status_code == 204
    event = db_session.query(UsageEvent).one()
    assert event.movie_id is None
    assert event.context == "selected_for_you"

    rejected = client.post(
        "/ui/events",
        json={
            "event_name": "personalized_recommendations_shown",
            "page": "discover",
            "context": "selected_for_you",
            "liked_titles": ["Blade Runner"],
        },
    )
    assert rejected.status_code == 422


def test_trusted_query_excludes_open_flags(db_session) -> None:
    db_session.add(MovieFlag(movie_id=1, reason="Verify identity"))
    db_session.commit()

    assert 1 in get_untrusted_movie_ids(db_session)
    trusted_ids = {
        movie_id for (movie_id,) in trusted_movie_query(db_session).with_entities(Movie.id).all()
    }
    assert 1 not in trusted_ids


def test_scoped_untrusted_lookup_only_checks_requested_movies(db_session) -> None:
    db_session.add(MovieFlag(movie_id=1, reason="Verify identity"))
    db_session.add(MovieFlag(movie_id=3, reason="Verify identity"))
    db_session.commit()

    assert get_untrusted_movie_ids(db_session, {1, 2}) == {1}


def test_poster_image_url_uses_one_smaller_tmdb_origin() -> None:
    assert (
        poster_image_url("https://media.themoviedb.org/t/p/w500/example.jpg")
        == "https://image.tmdb.org/t/p/w342/example.jpg"
    )
    assert (
        poster_image_url(
            "https://image.tmdb.org/t/p/original/example.jpg?language=en",
            "w500",
        )
        == "https://image.tmdb.org/t/p/w500/example.jpg?language=en"
    )
    assert poster_image_url("https://example.com/poster.jpg") == ("https://example.com/poster.jpg")


def test_discover_contains_all_collection_rails(client, db_session) -> None:
    for movie in db_session.query(Movie).all():
        movie.poster_url = f"https://image.tmdb.org/t/p/original/{movie.id}.jpg"
    db_session.commit()

    response = client.get("/ui/discover")
    assert response.status_code == 200
    for title in (
        "Recently Added",
        "Under 100 Minutes",
        "Highly Rated",
        "Hidden Gems",
        "Before 2000",
        "Edition Cuts",
    ):
        assert title in response.text
    assert 'data-preference-type="like"' in response.text
    assert 'data-preference-type="watchlist"' in response.text
    assert ">♡</button>" not in response.text
    assert ">▯</button>" not in response.text
    assert "library-card discover-rail-card library-card--poster-only" in response.text
    assert 'class="library-card__link"' in response.text
    assert 'class="library-card__media"' in response.text
    assert 'class="library-card__body"' not in response.text
    assert 'class="library-card__meta"' not in response.text
    assert 'class="library-card__genres"' not in response.text
    assert 'class="library-card__reasons"' not in response.text
    assert 'class="library-card__actions"' in response.text
    assert "Today’s shelves" not in response.text
    assert 'class="discover-sidebar"' not in response.text
    assert 'class="discover-index"' not in response.text
    assert "data-rail-next" in response.text
    assert "data-rail-progress" in response.text
    assert "Why this" in response.text
    assert 'fetchpriority="high"' in response.text
    assert 'fetchpriority="auto"' not in response.text
    assert "image.tmdb.org" not in response.text
    assert 'src="/ui/posters/' in response.text
    assert "data-deferred-poster" in response.text
    assert 'data-poster-src="/ui/posters/' in response.text
    eager_poster_sources = response.text.count('src="/ui/posters/') - response.text.count(
        'data-poster-src="/ui/posters/'
    )
    assert eager_poster_sources <= 4
    assert "/w185" in response.text
    assert 'loading="eager"' not in response.text
    assert response.text.count("library-card--poster-only") <= 36


def test_discover_rails_default_to_five_movies(db_session) -> None:
    for movie in db_session.query(Movie).all():
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
        movie.imdb_rating = movie.imdb_rating or 8.0
        movie.imdb_votes = movie.imdb_votes or 20_000
    db_session.commit()

    rails = _build_discover_rails(
        db_session,
        used_ids=set(),
        day=date(2026, 6, 14),
    )

    assert all(len(rail["movies"]) <= 5 for rail in rails)


def test_discover_rail_order_is_stable_and_rotates_by_day() -> None:
    first_day = date(2026, 6, 14)
    second_day = date(2026, 6, 15)

    first_order = [rail.key for rail in _ordered_rail_definitions(first_day)]
    repeated_order = [rail.key for rail in _ordered_rail_definitions(first_day)]
    second_order = [rail.key for rail in _ordered_rail_definitions(second_day)]

    assert first_order == repeated_order
    assert first_order != second_order
    assert set(first_order) == {rail.key for rail in RAIL_DEFINITIONS}


def test_daily_movie_rank_uses_stable_vault_identity() -> None:
    day = date(2026, 6, 14)

    assert _stable_daily_rank(day, "hidden-gems", "V0042") == _stable_daily_rank(
        day, "hidden-gems", "V0042"
    )
    assert _stable_daily_rank(day, "hidden-gems", "V0042") != _stable_daily_rank(
        day, "hidden-gems", "V0043"
    )


def test_discover_rails_keep_all_topics_and_do_not_repeat_movies(db_session) -> None:
    for movie in db_session.query(Movie).all():
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
        movie.imdb_rating = movie.imdb_rating or 8.0
        movie.imdb_votes = movie.imdb_votes or 20_000
    db_session.commit()

    rails = _build_discover_rails(
        db_session,
        used_ids=set(),
        limit=3,
        day=date(2026, 6, 14),
    )
    movie_ids = [movie.id for rail in rails for movie in rail["movies"] if movie.id is not None]

    assert {rail["key"] for rail in rails} == {definition.key for definition in RAIL_DEFINITIONS}
    assert len(movie_ids) == len(set(movie_ids))


def test_discover_explains_how_to_enable_personalization(client) -> None:
    response = client.get("/ui/discover")

    assert response.status_code == 200
    assert "Make Discover yours" in response.text
    assert "Like a movie in the Library" in response.text
    assert "data-selected-for-you" not in response.text


def test_selected_for_you_is_profile_specific_trusted_and_non_repeating(
    client, db_session, monkeypatch
) -> None:
    profile_a = Profile(name="User A", role="admin")
    profile_b = Profile(name="User B", role="reviewer")
    db_session.add_all([profile_a, profile_b])
    db_session.flush()

    liked_movie = db_session.get(Movie, 1)
    candidate = db_session.get(Movie, 2)
    flagged_candidate = db_session.get(Movie, 3)
    sci_fi = liked_movie.genres[0]

    for movie in (liked_movie, candidate, flagged_candidate):
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
        movie.imdb_rating = 8.0
        if sci_fi not in movie.genres:
            movie.genres.append(sci_fi)

    for movie in db_session.query(Movie).filter(Movie.id.between(4, 12)).all():
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
        movie.imdb_rating = 7.0
        movie.genres.append(sci_fi)

    db_session.add(MoviePreference(profile_id=profile_a.id, movie_id=liked_movie.id, liked=True))
    db_session.add(MoviePreference(profile_id=profile_a.id, movie_id=candidate.id, watchlist=True))
    db_session.add(MovieFlag(movie_id=flagged_candidate.id, reason="Verify identity"))
    db_session.commit()

    recommendations, genres = _pick_selected_for_you(db_session, profile_a.id, limit=12)
    recommendation_ids = {movie.id for movie in recommendations}

    assert genres[0] == sci_fi.name
    assert liked_movie.id not in recommendation_ids
    assert flagged_candidate.id not in recommendation_ids
    assert candidate.id not in recommendation_ids
    assert all(sci_fi in movie.genres for movie in recommendations)
    assert _pick_selected_for_you(db_session, profile_b.id) == ([], [])

    monkeypatch.setattr(
        "api.routers.ui.discover.get_daily_spotlight_movies",
        lambda _db, limit: [],
    )
    response = client.get("/ui/discover")
    assert response.status_code == 200
    assert "Selected for You" in response.text
    assert f"in {sci_fi.name}." in response.text
    assert "data-selected-for-you" in response.text
    assert response.text.count(f'href="/ui/movies/{candidate.id}"') == 1


def test_discover_rails_only_surface_movies_with_posters(db_session) -> None:
    for key in (
        "recently-added",
        "under-100",
        "highly-rated",
        "hidden-gems",
        "before-2000",
        "edition-cuts",
    ):
        assert all(movie.poster_url for movie in _rail_candidates(db_session, key))
