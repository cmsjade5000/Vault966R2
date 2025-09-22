from fastapi.testclient import TestClient

from api.schemas.movie import MovieCreate


def test_create_person_requires_token(client: TestClient):
    response = client.post(
        "/people/",
        json={"name": "Unauthorized User"},
    )
    assert response.status_code == 401


def test_create_movie_with_token(client: TestClient, admin_headers: dict[str, str]):
    payload = MovieCreate(
        title="Auth Movie",
        year=2020,
        runtime=120,
        genres=[],
        moods=[],
    )
    response = client.post(
        "/movies/",
        json=payload.model_dump(),
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Auth Movie"
