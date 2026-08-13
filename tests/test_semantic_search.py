import httpx
import pytest
from fastapi.testclient import TestClient

from api.services import semantic_search
from api.services.semantic_search import (
    SemanticSearchError,
    apply_semantic_query_overrides,
    parse_semantic_intent,
    semantic_query_forces_animation,
)
from core.movie_filters import MovieFilterParams


def test_semantic_search_falls_back_when_disabled(client: TestClient) -> None:
    response = client.post("/api/search/semantic", json={"query": "Matrix"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword"
    assert payload["notice"]
    assert any(item["title"] == "The Matrix" for item in payload["items"])


def test_semantic_search_falls_back_on_sqlite(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(semantic_search.settings, "semantic_search_enabled", True)
    monkeypatch.setattr(semantic_search.settings, "llm_api_key", "test-key")
    response = client.post("/api/search/semantic", json={"query": "Blade Runner"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "keyword"
    assert payload["notice"]
    assert any(item["title"] == "Blade Runner" for item in payload["items"])


def test_semantic_query_animation_override() -> None:
    params = MovieFilterParams(q=None)
    updated = apply_semantic_query_overrides("cozy animated family adventure", params)
    assert "Animation" in updated.genres

    with_genre = MovieFilterParams(q=None, genres=("Animation",))
    updated_again = apply_semantic_query_overrides("animated", with_genre)
    assert updated_again.genres.count("Animation") == 1


def test_semantic_query_forces_animation() -> None:
    assert semantic_query_forces_animation("Animated family adventure") is True
    assert semantic_query_forces_animation("cozy animation") is True
    assert semantic_query_forces_animation("family drama") is False


def test_semantic_intent_decade_and_runtime() -> None:
    params = MovieFilterParams(q=None)
    intent = parse_semantic_intent("90s sci-fi under 100", params)
    assert intent.params.year_min == 1990
    assert intent.params.year_max == 1999
    assert intent.params.runtime_max == 100
    assert "Science Fiction" in intent.boost_genres

    params_with_year = MovieFilterParams(q=None, year_min=2000, year_max=2010)
    intent_no_override = parse_semantic_intent("90s drama", params_with_year)
    assert intent_no_override.params.year_min == 2000
    assert intent_no_override.params.year_max == 2010


def test_embedding_failure_does_not_retain_authorization_secret(monkeypatch) -> None:
    sentinel = "SENTINEL_EMBEDDING_AUTH_SECRET"
    monkeypatch.setattr(semantic_search.settings, "llm_api_key", sentinel)
    monkeypatch.setattr(semantic_search, "EMBEDDING_MAX_RETRIES", 1)
    monkeypatch.setattr(semantic_search.time, "sleep", lambda _seconds: None)

    def fail_post(url, *, headers, json, timeout):
        request = httpx.Request("POST", url, headers=headers, json=json)
        raise httpx.RequestError(
            f"connection reset; Authorization: Bearer {sentinel}",
            request=request,
        )

    monkeypatch.setattr(semantic_search.httpx, "post", fail_post)

    with pytest.raises(SemanticSearchError) as error_info:
        semantic_search._fetch_embeddings(["a movie description"])

    seen: set[int] = set()
    chain_messages = []
    pending: list[BaseException] = [error_info.value]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        assert not isinstance(current, httpx.HTTPError)
        chain_messages.append(str(current))
        pending.extend(
            linked for linked in (current.__cause__, current.__context__) if linked is not None
        )
    diagnostic = "\n".join(chain_messages)

    assert sentinel not in diagnostic
    assert "[REDACTED]" in diagnostic
    assert "connection reset" in diagnostic
