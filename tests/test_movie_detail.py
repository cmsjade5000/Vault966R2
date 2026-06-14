import pytest
from sqlalchemy import text
from fastapi.testclient import TestClient

from api.db import get_db
from api.models.movie import Genre, Mood, Movie
from api.models.person import Person, Role, RoleType


def _db_session(client: TestClient):
    override = client.app.dependency_overrides[get_db]
    generator = override()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


@pytest.fixture()
def detail_movie_setup(client: TestClient):
    for db in _db_session(client):
        genre_sf = Genre(name="Cyberpunk")
        mood_dreamy = Mood(name="Dreamy")
        db.add_all([genre_sf, mood_dreamy])
        db.flush()

        movie = Movie(
            title="Test Detail Movie",
            year=2019,
            runtime=118,
            plot="A deep dive into dream heists.",
            imdb_id="tt9999999",
            tmdb_id=999999,
            imdb_rating=8.7,
            imdb_votes=123456,
            rt_score=91,
            where_to_watch="Netflix; Prime Video",
            languages="English, Japanese",
            countries="USA",
            collection="Dream Saga",
        )
        movie.genres.append(genre_sf)
        movie.moods.append(mood_dreamy)
        db.add(movie)
        db.flush()

        person = Person(name="Case Worker", imdb_id="nm0000001", tmdb_id=1)
        db.add(person)
        db.flush()

        role = Role(
            movie_id=movie.id,
            person_id=person.id,
            role_type=RoleType.ACTOR,
            character_name="Dreamer",
            billing_order=1,
        )
        db.add(role)

        similar_movie = Movie(
            title="Dream Runner",
            year=2020,
            runtime=110,
            imdb_id="tt8888888",
            tmdb_id=888888,
            plot="Similar vibes",
        )
        similar_movie.genres.append(genre_sf)
        similar_movie.moods.append(mood_dreamy)
        db.add(similar_movie)

        db.commit()
        yield movie.id


def test_movie_detail_api(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["title"] == "Test Detail Movie"
    assert payload["imdb_rating"] == 8.7
    assert payload["roles"][0]["person"]["name"] == "Case Worker"
    assert payload["where_to_watch"] == ["Netflix", "Prime Video"]
    assert payload["similar"]
    assert payload["flagged"] is False
    assert payload["top_billed"][0]["name"] == "Case Worker"
    assert payload["top_billed"][0]["character"] == "Dreamer"


def test_movie_detail_template(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    resp = client.get(f"/ui/movies/{movie_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "Case Worker" in html
    assert "Top billed" in html
    assert "data-copy-vault" in html
    assert 'data-vault-busy-message="Returning to the Library…"' in html
    assert "js/back_link.js?v=" in html
    assert "css/movies.css?v=" in html
    assert "css/movie_detail.css?v=" in html
    assert "css/movie_components.css?v=" in html
    assert "js/movie_detail.js?v=" in html
    assert "js/movie_preferences.js?v=" in html
    assert "js/movie_detail_edit.js?v=" in html
    assert "js/movies_page.js" not in html
    assert "data-poster-focus" in html
    assert "data-poster-focus-backdrop" in html
    assert 'aria-label="Enlarge Test Detail Movie poster"' in html
    assert 'class="library-grid"' in html
    assert 'class="library-card"' in html
    assert 'class="library-card__actions"' in html
    assert 'class="preference-icon' in html
    assert 'class="preference-button' not in html
    assert "detail-rec-card" not in html
    assert "Pair with this" not in html
    assert "More like this" in html


def test_movie_detail_renders_spotlight_context_when_requested(
    client: TestClient, detail_movie_setup
):
    movie_id = detail_movie_setup

    response = client.get(f"/ui/movies/{movie_id}?spotlight=1")

    assert response.status_code == 200
    assert "spotlight-banner" in response.text


def test_movie_detail_accepts_json_languages_and_countries(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    for db in _db_session(client):
        movie = db.query(Movie).filter(Movie.id == movie_id).one()
        movie.languages = ["English", "en"]
        movie.countries = ["United States of America", "US"]
        db.add(movie)
        db.commit()

    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["languages"] == ["English", "en"]
    assert payload["countries"] == ["United States of America", "US"]
    assert payload["languages_iso"] == ["en"]
    assert payload["countries_iso"] == ["US"]
    assert "English" in payload["languages_display"]
    assert "United States" in payload["countries_display"]


def test_movie_detail_flag_status(
    client: TestClient, detail_movie_setup, admin_headers: dict[str, str]
):
    movie_id = detail_movie_setup
    client.post(
        f"/movies/{movie_id}/flag",
        json={"reason": "Poster"},
        headers=admin_headers,
    )
    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    assert resp.json()["flagged"] is True


def test_movie_detail_handles_dict_languages_and_countries(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    for db in _db_session(client):
        movie = db.query(Movie).filter(Movie.id == movie_id).one()
        movie.languages = {"en": "English", "fr": "French"}
        movie.countries = {"US": "United States"}
        db.add(movie)
        db.commit()

    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    payload = resp.json()
    assert "en" in payload["languages"]
    assert "US" in payload["countries"]


def test_movie_detail_skips_roles_missing_people(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    for db in _db_session(client):
        orphan_role = Role(
            movie_id=movie_id,
            person_id=999999,
            role_type=RoleType.ACTOR,
            character_name="Ghost",
            billing_order=2,
        )
        db.add(orphan_role)
        db.commit()

    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    payload = resp.json()
    assert all(role["person_id"] != 999999 for role in payload["roles"])


def test_movie_detail_handles_invalid_role_type(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    for db in _db_session(client):
        person = Person(name="Edge Case", imdb_id="nm2222222", tmdb_id=2222)
        db.add(person)
        db.flush()
        db.execute(
            text(
                """
                INSERT INTO roles (movie_id, person_id, role_type, character_name, billing_order)
                VALUES (:movie_id, :person_id, :role_type, :character_name, :billing_order)
                """
            ),
            {
                "movie_id": movie_id,
                "person_id": person.id,
                "role_type": "PRODUCER",
                "character_name": "Unknown",
                "billing_order": 2,
            },
        )
        db.commit()

    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
