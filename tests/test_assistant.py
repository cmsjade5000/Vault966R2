from fastapi.testclient import TestClient

from api.services.assistant import AssistantTemplate


def test_assistant_get_with_session_cookie_does_not_call_provider(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    from api.routers import assistant as assistant_router

    login_profile(1)

    def fail_provider(query, *, movies, client=None):
        raise AssertionError("GET /api/assistant must not call the assistant provider")

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fail_provider)

    response = client.get("/api/assistant", params={"q": "sci-fi", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["reply"].startswith("Vault pick")
    assert payload["movies"]


def test_assistant_post_with_session_cookie_requires_same_origin(
    client: TestClient,
    login_profile,
) -> None:
    login_profile(1)

    response = client.post("/api/assistant", json={"query": "sci-fi", "limit": 2})

    assert response.status_code == 403


def test_assistant_post_same_origin_session_can_use_provider(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    from api.routers import assistant as assistant_router

    calls = []

    def fake_provider(query, *, movies, client=None):
        calls.append({"query": query, "movies": list(movies)})
        return AssistantTemplate(
            template="Try {{movie_1}}.",
            pick_count=1,
            followup="",
        )

    login_profile(1)
    monkeypatch.setattr(assistant_router, "generate_assistant_template", fake_provider)

    response = client.post(
        "/api/assistant",
        json={"query": "sci-fi", "limit": 2},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert response.json()["reply"].startswith("Try ")
    assert calls


def test_assistant_post_with_token_can_use_provider_without_origin(
    client: TestClient,
    monkeypatch,
) -> None:
    from api.config import settings
    from api.routers import assistant as assistant_router

    calls = []

    def fake_provider(query, *, movies, client=None):
        calls.append(query)
        return AssistantTemplate(
            template="Try {{movie_1}}.",
            pick_count=1,
            followup="",
        )

    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")
    monkeypatch.setattr(assistant_router, "generate_assistant_template", fake_provider)

    response = client.post(
        "/api/assistant",
        json={"query": "sci-fi", "limit": 2},
        headers={"Authorization": "Bearer assistant-token"},
    )

    assert response.status_code == 200
    assert response.json()["reply"].startswith("Try ")
    assert calls == ["sci-fi"]


def test_assistant_get_with_token_is_cache_only(
    client: TestClient,
    monkeypatch,
) -> None:
    from api.config import settings
    from api.routers import assistant as assistant_router

    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")

    def fail_provider(query, *, movies, client=None):
        raise AssertionError("GET /api/assistant must not call the assistant provider")

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fail_provider)

    response = client.get(
        "/api/assistant",
        params={"q": "sci-fi"},
        headers={"Authorization": "Bearer assistant-token"},
    )

    assert response.status_code == 200
    assert response.json()["movies"]
