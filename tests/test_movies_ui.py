from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.person import Person, Role, RoleType
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

    by_vault_id = client.get("/ui/movies", params={"q": "V0001"})
    by_year = client.get("/ui/movies", params={"q": "1982"})
    by_person = client.get("/ui/movies", params={"q": "Ridley Scott"})

    assert "Blade Runner" in by_vault_id.text
    assert "Blade Runner" in by_year.text
    assert "Blade Runner" in by_person.text


def test_flags_page_lists_flagged_movies(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post("/movies/1/flag", json={"reason": "Metadata cleanup"}, headers=admin_headers)
    assert resp.status_code == 200

    page = client.get("/ui/flags")
    assert page.status_code == 200
    html = page.text
    assert "Flags" in html
    assert "Metadata cleanup" in html


def test_review_route_redirects_to_human_review_queue(client: TestClient) -> None:
    resp = client.get("/ui/movies/review", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/ui/review"


def test_review_queue_shows_detected_issue_and_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.title = "Blade Runner (1981)"
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.get("/ui/review")

    assert response.status_code == 200
    assert "Human Review" in response.text
    assert "Title and year disagree" in response.text
    assert "V0001" in response.text


def test_review_checked_removes_movie_from_queue(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post("/ui/review/1/checked", follow_redirects=True)

    assert response.status_code == 200
    assert "V0001 marked as checked." in response.text
    assert "Year is missing" not in response.text


def test_vault_review_actions_preserve_vault_category(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post("/ui/review/1/checked?view=vault", follow_redirects=False)

    assert response.status_code == 303
    assert "view=vault" in response.headers["location"]


def test_review_needs_fix_creates_flag_with_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post("/ui/review/1/needs-fix", follow_redirects=True)
    flags = client.get("/ui/flags")

    assert response.status_code == 200
    assert "V0001 added to Flags." in response.text
    assert "V0001" in flags.text
    assert "Human review" in flags.text


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
