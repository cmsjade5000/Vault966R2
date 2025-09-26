import pytest
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


def test_movie_detail_template(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    resp = client.get(f"/ui/movies/{movie_id}")
    assert resp.status_code == 200
    html = resp.text
    assert "Dream Runner" in html
    assert "Case Worker" in html


def test_movie_detail_flag_status(client: TestClient, detail_movie_setup):
    movie_id = detail_movie_setup
    client.post(f"/movies/{movie_id}/flag", json={"reason": "Poster"})
    resp = client.get(f"/movies/{movie_id}/detail")
    assert resp.status_code == 200
    assert resp.json()["flagged"] is True
