import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.models.vault_id import RetiredVaultId
from api.schemas.movie import MovieCreate


@pytest.fixture()
def auth_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "admin_token", "testtoken")
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")


def test_admin_bearer_reaches_only_admin_api_operations_without_session(
    client: TestClient,
    admin_headers: dict[str, str],
    auth_enabled,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.get_collection_recommendation",
        lambda db, force=False: "bearer recommendation",
    )
    flags = client.get("/movies/flags", headers=admin_headers)
    person = client.post(
        "/people/",
        json={"name": "Bearer Admin"},
        headers=admin_headers,
    )
    movie = client.patch(
        "/movies/1",
        json={"title": "Bearer Updated"},
        headers=admin_headers,
    )
    recommendation = client.post(
        "/api/collection-health/recommendation/refresh",
        headers=admin_headers,
    )
    people_index = client.get("/people/", headers=admin_headers)
    profiles = client.get(
        "/api/profiles",
        headers=admin_headers,
        follow_redirects=False,
    )

    assert flags.status_code == 200
    assert person.status_code == 201
    assert movie.status_code == 200
    assert movie.json()["title"] == "Bearer Updated"
    assert recommendation.status_code == 200
    assert recommendation.json() == {"recommendation": "bearer recommendation"}
    assert people_index.status_code == 401
    assert profiles.status_code == 401
    assert profiles.json()["error_code"] == "auth_required"


@pytest.mark.parametrize(
    ("admin_token", "headers"),
    [
        pytest.param("testtoken", {}, id="missing"),
        pytest.param(
            "testtoken",
            {"Authorization": "Bearer wrong-token"},
            id="invalid",
        ),
        pytest.param(
            "testtoken",
            {"Authorization": "Basic testtoken"},
            id="wrong-scheme",
        ),
        pytest.param(
            "testtoken",
            {"Authorization": "Bearer assistant-token"},
            id="assistant-token",
        ),
        pytest.param(
            None,
            {"Authorization": "Bearer testtoken"},
            id="not-configured",
        ),
    ],
)
def test_admin_api_rejects_missing_invalid_and_unconfigured_tokens(
    client: TestClient,
    auth_enabled,
    monkeypatch,
    admin_token: str | None,
    headers: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "admin_token", admin_token)

    response = client.get("/movies/flags", headers=headers)

    assert response.status_code == 401
    assert response.json()["error_code"] == "auth_required"


def test_admin_bearer_does_not_replace_browser_session(
    client: TestClient,
    admin_headers: dict[str, str],
    auth_enabled,
    login_profile,
    monkeypatch,
) -> None:
    bearer_only = client.get(
        "/ui/movies",
        headers=admin_headers,
        follow_redirects=False,
    )

    assert bearer_only.status_code == 302
    assert bearer_only.headers["location"] == "/login"

    login_profile(1)
    session = client.get("/ui/movies", follow_redirects=False)
    monkeypatch.setattr("api.routers.movies.get_movie_detail", lambda *args, **kwargs: None)
    provider_work = client.post("/movies/1/detail", headers=admin_headers)

    assert session.status_code == 200
    assert provider_work.status_code == 403


def test_admin_bearer_provider_work_remains_budgeted(
    client: TestClient,
    admin_headers: dict[str, str],
    auth_enabled,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.get_collection_recommendation",
        lambda db, force=False: "bearer recommendation",
    )

    responses = [
        client.post(
            "/api/collection-health/recommendation/refresh",
            headers=admin_headers,
        )
        for _ in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429


def test_assistant_token_exception_remains_separate_from_admin_bearer(
    client: TestClient,
    admin_headers: dict[str, str],
    auth_enabled,
) -> None:
    assistant = client.get(
        "/api/assistant",
        params={"q": "sci-fi"},
        headers={"Authorization": "Bearer assistant-token"},
    )
    admin = client.get(
        "/api/assistant",
        params={"q": "sci-fi"},
        headers=admin_headers,
    )

    assert assistant.status_code == 200
    assert admin.status_code == 401
    assert admin.json()["message"] == "Assistant token required."


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
