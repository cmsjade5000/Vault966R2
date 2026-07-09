import pytest
from fastapi.testclient import TestClient

from api.schemas.llm_filters import LlmMovieFilters
from api.services.llm_filters import LlmFilterError, LlmProviderUnavailable


def test_llm_search_uses_generated_filters(client: TestClient, monkeypatch) -> None:
    from api.routers import movies as movies_router

    def fake_generate_llm_filters(query, *, allowed_genres, allowed_moods, client=None):
        return LlmMovieFilters(
            genres=["Sci-Fi"],
            moods=["Exciting"],
            order_by="title_asc",
        )

    monkeypatch.setattr(movies_router, "generate_llm_filters", fake_generate_llm_filters)

    response = client.post("/movies/search/llm", json={"query": "exciting sci-fi"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["genres"] == ["Sci-Fi"]
    assert payload["filters"]["moods"] == ["Exciting"]
    assert payload["total"] == 1
    assert payload["items"][0]["title"] == "The Matrix"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_message"),
    [
        (
            LlmProviderUnavailable("LLM_API_KEY is not configured"),
            503,
            "Smart search is temporarily unavailable.",
        ),
        (
            LlmFilterError("LLM request failed: connection reset"),
            502,
            "Smart search could not be completed. Please try again.",
        ),
    ],
)
def test_llm_search_hides_provider_error_details(
    client: TestClient,
    monkeypatch,
    error: Exception,
    expected_status: int,
    expected_message: str,
) -> None:
    from api.routers import movies as movies_router

    def fail_generate_llm_filters(*args, **kwargs):
        raise error

    monkeypatch.setattr(movies_router, "generate_llm_filters", fail_generate_llm_filters)

    response = client.post("/movies/search/llm", json={"query": "moody sci-fi"})

    assert response.status_code == expected_status
    assert response.json()["message"] == expected_message
    assert "LLM" not in response.json()["message"]
