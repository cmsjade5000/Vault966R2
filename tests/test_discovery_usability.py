from datetime import date

from sqlalchemy import event

from api.models.usage_event import UsageEvent
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.profile import MoviePreference, Profile
from api.routers.ui.discover import (
    RAIL_DEFINITIONS,
    _build_discover_rails,
    _build_tonight_shortlist,
    _ordered_rail_definitions,
    _pick_selected_for_you,
    _rail_candidates,
    _stable_daily_rank,
)
from api.services.ui.templates import poster_image_url
from api.services.trusted_movies import get_untrusted_movie_ids, trusted_movie_query
from core.genres import split_and_normalize


def _make_discover_candidates(db_session) -> None:
    for movie in db_session.query(Movie).limit(16).all():
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
        movie.imdb_rating = movie.imdb_rating or 8.0
        movie.imdb_votes = movie.imdb_votes or 20_000
    db_session.commit()


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

    sort_event = client.post(
        "/ui/events",
        json={
            "event_name": "sort_changed",
            "page": "library",
            "context": "title_asc",
        },
    )
    assert sort_event.status_code == 204
    assert db_session.query(UsageEvent).count() == 2

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
    assert db_session.query(UsageEvent).count() == 2


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


def test_discover_page_renders_watch_tonight_surface(client, db_session) -> None:
    _make_discover_candidates(db_session)
    response = client.get("/ui/discover")

    assert response.status_code == 200
    html = response.text
    assert "Watch Tonight" in html
    assert "Tonight’s Best Bet" in html
    assert "Tonight’s Shortlist" in html
    assert "Explore the Vault" in html
    assert 'href="/ui/movies?preset=under-100&amp;view=grid&amp;page=1"' in html
    assert 'href="/ui/watchlist"' in html
    assert 'class="nav-link is-active"' in html
    assert ">Discover</a" in html


def test_discover_page_uses_preference_controls_and_safe_event_contexts(client, db_session) -> None:
    _make_discover_candidates(db_session)
    response = client.get("/ui/discover")

    assert response.status_code == 200
    html = response.text
    assert 'data-preference-type="like"' in html
    assert 'data-preference-type="watchlist"' in html
    assert 'data-event-context="tonight_shortlist"' in html
    assert "liked_titles" not in html
    assert "search_text" not in html


def test_discover_page_keeps_the_initial_render_bounded(client, db_session) -> None:
    _make_discover_candidates(db_session)
    query_count = 0

    def count_query(*_args) -> None:
        nonlocal query_count
        query_count += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_query)
    try:
        response = client.get("/ui/discover")
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    assert response.status_code == 200
    html = response.text
    assert query_count <= 50
    assert html.count("<img") <= 13
    assert len(response.content) < 80_000
    assert "data-deferred-poster" not in html
    assert "data-rail-viewport" not in html
    assert "data-rail-next" not in html


def test_tonight_shortlist_is_bounded_stable_and_eager_loads_moods(db_session) -> None:
    _make_discover_candidates(db_session)
    day = date(2026, 6, 14)

    first = _build_tonight_shortlist(db_session, used_ids=set(), limit=7, day=day)
    repeated = _build_tonight_shortlist(db_session, used_ids=set(), limit=7, day=day)

    assert len(first) <= 7
    assert [movie.id for movie in first] == [movie.id for movie in repeated]
    assert len({movie.id for movie in first}) == len(first)
    assert all("moods" in movie.__dict__ for movie in first)


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


def test_selected_for_you_is_profile_specific_trusted_and_non_repeating(db_session) -> None:
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
