from fastapi.testclient import TestClient

from api.config import settings
from api.routers import assistant as assistant_router
from api.services.assistant import AssistantTemplate


def test_assistant_get_with_session_uses_local_reply_without_provider(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    login_profile(1)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")

    calls = 0

    def fail_if_provider_called(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("GET /api/assistant must not trigger provider work")

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fail_if_provider_called)

    response = client.get("/api/assistant", params={"q": "sci-fi", "limit": 3})

    assert response.status_code == 200
    assert response.json()["reply"].startswith("Vault picks:")
    assert calls == 0


def test_assistant_get_with_token_uses_local_reply_without_provider(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")

    calls = 0

    def fail_if_provider_called(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("GET /api/assistant must not trigger provider work")

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fail_if_provider_called)

    response = client.get(
        "/api/assistant",
        params={"q": "sci-fi", "limit": 3},
        headers={"Authorization": "Bearer assistant-token"},
    )

    assert response.status_code == 200
    assert response.json()["reply"].startswith("Vault picks:")
    assert calls == 0


def test_assistant_post_with_session_requires_same_origin_before_provider(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    login_profile(1)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")

    calls = 0

    def fake_provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        return AssistantTemplate(
            template="Try {{movie_1}}.",
            pick_count=1,
            followup="Enjoy the show.",
        )

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fake_provider)

    blocked = client.post("/api/assistant", json={"query": "sci-fi", "limit": 3})

    assert blocked.status_code == 403
    assert calls == 0

    allowed = client.post(
        "/api/assistant",
        json={"query": "sci-fi", "limit": 3},
        headers={"Origin": "http://testserver"},
    )

    assert allowed.status_code == 200
    assert allowed.json()["reply"].endswith("Enjoy the show.")
    assert calls == 1


def test_assistant_post_with_token_can_use_provider_without_browser_origin(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")

    calls = 0

    def fake_provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        return AssistantTemplate(
            template="Try {{movie_1}}.",
            pick_count=1,
            followup="Enjoy the show.",
        )

    monkeypatch.setattr(assistant_router, "generate_assistant_template", fake_provider)

    response = client.post(
        "/api/assistant",
        json={"query": "sci-fi", "limit": 3},
        headers={"Authorization": "Bearer assistant-token"},
    )

    assert response.status_code == 200
    assert response.json()["reply"].endswith("Enjoy the show.")
    assert calls == 1
