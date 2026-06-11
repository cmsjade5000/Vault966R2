from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.movie_review import MovieReviewCheck
from api.models.person import Person, Role, RoleType
from api.services.movie_review import (
    apply_all_title_year_corrections,
    detect_review_issues,
    get_review_queue,
)
from api.services.ui.grid import FILTER_COOKIE_NAME


def test_movies_grid_persists_filters_via_cookie(client: TestClient) -> None:
    first = client.get(
        "/ui/movies",
        params={
            "genres": "Science Fiction",
            "order_by": "runtime_asc",
        },
    )
    assert first.status_code == 200
    assert client.cookies.get(FILTER_COOKIE_NAME) is not None

    second = client.get("/ui/movies")
    assert second.status_code == 200
    html = second.text
    assert 'id="genres-input" value="Science Fiction"' in html
    assert 'option value="runtime_asc" selected' in html
    assert "Blade Runner" in html
    assert "Toy Story" not in html


def test_movies_grid_filters_by_mood(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"moods": "Moody"})
    assert response.status_code == 200
    html = response.text
    assert "Blade Runner" in html
    assert "The Matrix" not in html


def test_library_search_is_prominent_and_searches_identity_fields(
    client: TestClient, db_session
) -> None:
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()
    movie.vault_id = "V0001"
    director = Person(name="Ridley Scott")
    db_session.add(director)
    db_session.flush()
    db_session.add(
        Role(
            movie_id=movie.id,
            person_id=director.id,
            role_type=RoleType.DIRECTOR,
        )
    )
    db_session.commit()

    page = client.get("/ui/movies")

    assert "Search your Vault" in page.text
    assert "director, actor, genre, or IMDb ID" in page.text
    assert 'aria-label="Open filters"' in page.text
    assert 'aria-label="Random trusted movie"' in page.text

    by_vault_id = client.get("/ui/movies", params={"q": "V0001"})
    by_year = client.get("/ui/movies", params={"q": "1982"})
    by_person = client.get("/ui/movies", params={"q": "Ridley Scott"})

    assert "Blade Runner" in by_vault_id.text
    assert "Blade Runner" in by_year.text
    assert "Blade Runner" in by_person.text


def test_health_page_uses_vault_health_title_and_prioritizes_metrics(
    client: TestClient,
) -> None:
    response = client.get("/ui/movies/health")

    assert response.status_code == 200
    assert "<h1>Vault Health</h1>" in response.text
    assert "Vault overview" in response.text
    assert "Review workbench" in response.text
    assert "Source synchronization" in response.text
    assert 'href="#metadata-gaps"' not in response.text
    assert 'href="/ui/review"' not in response.text
    assert ">Review</a" not in response.text
    assert "Flic Recommendation" not in response.text
    assert "Add a movie" not in response.text


def test_flags_page_lists_flagged_movies(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post("/movies/1/flag", json={"reason": "Metadata cleanup"}, headers=admin_headers)
    assert resp.status_code == 200

    page = client.get("/ui/movies/health?view=flags")
    assert page.status_code == 200
    html = page.text
    assert "Flags" in html
    assert "Metadata cleanup" in html


def test_review_route_redirects_to_vault_health_workbench(client: TestClient) -> None:
    resp = client.get("/ui/movies/review", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/ui/movies/health?view=vault#review-workbench"


def test_review_queue_shows_detected_issue_and_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.title = "Blade Runner (1981)"
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.get("/ui/movies/health")

    assert response.status_code == 200
    assert "Review workbench" in response.text
    assert "Title and year disagree" in response.text
    assert "V0001" in response.text


def test_title_year_authority_updates_year_and_preserves_other_flag_issues(
    db_session,
) -> None:
    first = db_session.get(Movie, 1)
    first.title = "Blade Runner (1981)"
    first.year = 1982
    first.flag = MovieFlag(
        reason="Human review",
        notes="Title and year disagree",
    )
    second = db_session.get(Movie, 2)
    second.title = "The Matrix (2001)"
    second.year = 1999
    second.flag = MovieFlag(
        reason="Human review",
        notes="Title and year disagree; No source IDs",
    )
    db_session.add(
        MovieReviewCheck(
            movie_id=first.id,
            issue_type="title_year_conflict",
            issue_fingerprint=detect_review_issues(first)[0].fingerprint,
            decision="needs_fix",
        )
    )
    db_session.commit()

    result = apply_all_title_year_corrections(db_session, profile_id=1)

    db_session.expire_all()
    assert result.movie_count == 2
    assert result.cleared_flag_count == 1
    assert db_session.get(Movie, 1).year == 1981
    assert db_session.get(Movie, 1).flag is None
    assert db_session.get(Movie, 2).year == 2001
    assert db_session.get(Movie, 2).flag.notes == "No source IDs"
    assert (
        db_session.query(MovieReviewCheck)
        .filter(MovieReviewCheck.movie_id == first.id)
        .one()
        .decision
        == "title_year_applied"
    )


def test_review_checked_removes_movie_from_queue(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post("/ui/movies/health/review/1/checked", follow_redirects=True)

    assert response.status_code == 200
    assert "V0001 marked as checked." in response.text
    assert "Year is missing" not in response.text


def test_vault_review_actions_preserve_vault_category(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/1/checked?view=vault",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "view=vault" in response.headers["location"]


def test_review_needs_fix_creates_flag_with_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/1/needs-fix",
        follow_redirects=True,
    )
    flags = client.get("/ui/movies/health?view=flags")

    assert response.status_code == 200
    assert "V0001 added to Flags." in response.text
    assert "V0001" in flags.text
    assert "Human review" in flags.text


def test_bulk_review_needs_fix_moves_all_open_checks_to_flags(
    client: TestClient, db_session
) -> None:
    movies = db_session.query(Movie).order_by(Movie.id).limit(2).all()
    for index, movie in enumerate(movies, start=1):
        movie.year = None
        movie.vault_id = f"V{index:04d}"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/vault/needs-fix-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Moved%202%20Vault%20checks%20to%20Flags" in response.headers["location"]
    assert get_review_queue(db_session)[0] == []
    flags = db_session.query(MovieFlag).order_by(MovieFlag.movie_id).all()
    assert [flag.movie_id for flag in flags] == [movie.id for movie in movies]
    assert all(flag.reason == "Human review" for flag in flags)
    assert all(flag.notes == "Year is missing" for flag in flags)


def test_movie_detail_shows_review_bar(client: TestClient) -> None:
    resp = client.get("/ui/movies/1", params={"review": "1"})
    assert resp.status_code == 200
    html = resp.text
    assert "Review mode" in html
    assert 'href="/ui/movies/2?review=1"' in html


def test_missing_details_page_renders(client: TestClient) -> None:
    resp = client.get("/ui/movies/health/missing")
    assert resp.status_code == 200
    html = resp.text
    assert "Missing runtime" in html
    assert "Missing synopsis" in html
    assert "Missing artwork" in html
