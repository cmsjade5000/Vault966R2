from api.models.usage_event import UsageEvent
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.routers.ui.discover import _rail_candidates
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


def test_trusted_query_excludes_open_flags(db_session) -> None:
    db_session.add(MovieFlag(movie_id=1, reason="Verify identity"))
    db_session.commit()

    assert 1 in get_untrusted_movie_ids(db_session)
    trusted_ids = {
        movie_id for (movie_id,) in trusted_movie_query(db_session).with_entities(Movie.id).all()
    }
    assert 1 not in trusted_ids


def test_discover_contains_all_collection_rails(client, db_session) -> None:
    for movie in db_session.query(Movie).all():
        movie.poster_url = f"https://example.com/posters/{movie.id}.jpg"
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
