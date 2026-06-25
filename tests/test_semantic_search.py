from fastapi.testclient import TestClient

from api.services import semantic_search
from api.services.semantic_search import (
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
