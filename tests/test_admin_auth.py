from fastapi.testclient import TestClient

from api.models.vault_id import RetiredVaultId
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
        awards="Won an award",
        certificate="PG-13",
        keywords=["mystery", "archive"],
        imdb_rating=7.5,
        rt_score=88,
        where_to_watch=["Netflix"],
        languages=["English"],
        countries=["United States"],
        collection="Auth Collection",
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
    assert body["awards"] == "Won an award"
    assert body["certificate"] == "PG-13"
    assert body["keywords"] == ["mystery", "archive"]
    assert body["imdb_rating"] == 7.5
    assert body["rt_score"] == 88
    assert body["where_to_watch"] == ["Netflix"]
    assert body["languages_iso"] == ["en"]
    assert body["countries_iso"] == ["US"]
    assert body["collection"] == "Auth Collection"
    body = response.json()
    assert body["title"] == "Auth Movie"


def test_create_movie_rejects_retired_vault_id(
    client: TestClient,
    db_session,
    admin_headers: dict[str, str],
):
    db_session.add(
        RetiredVaultId(
            vault_id="V0087",
            source="legacy_gap",
            reason="Known legacy Vault ID gap reserved to prevent reuse.",
        )
    )
    db_session.commit()
    payload = MovieCreate(title="Retired ID Movie", vault_id="V0087", genres=[], moods=[])

    response = client.post(
        "/movies/",
        json=payload.model_dump(),
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Vault ID V0087 is retired and cannot be reused"
