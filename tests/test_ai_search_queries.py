import pytest
from fastapi.testclient import TestClient

from api.schemas.ai_search import SearchPlan
from api.services.ai_search import AiSearchError, AiSearchProviderUnavailable


@pytest.mark.parametrize(
    "query, plan, expected_titles, expected_total",
    [
        (
            "moody sci-fi from the 80s",
            SearchPlan(genres=["Sci-Fi"], moods=["Moody"], year_min=1980, year_max=1989),
            ["Blade Runner"],
            1,
        ),
        (
            "exciting sci-fi late 90s",
            SearchPlan(genres=["Sci-Fi"], moods=["Exciting"], year_min=1995, year_max=2000),
            ["The Matrix"],
            1,
        ),
        (
            "family animation under 90 minutes",
            SearchPlan(genres=["Animation"], moods=["Family"], runtime_max=90),
            ["Toy Story"],
            1,
        ),
        (
            "library movies from 2001",
            SearchPlan(genres=["Library"], year_min=2001, year_max=2001),
            ["Movie 01", "Movie 06", "Movie 11", "Movie 16", "Movie 21", "Movie 26"],
            6,
        ),
        (
            "anything with matrix in title",
            SearchPlan(q="matrix"),
            ["The Matrix"],
            1,
        ),
        (
            "latest sci-fi",
            SearchPlan(genres=["Sci-Fi"], order_by="year_desc"),
            ["The Matrix", "Blade Runner"],
            2,
        ),
    ],
)
def test_ai_search_queries(
    client: TestClient,
    monkeypatch,
    query: str,
    plan: SearchPlan,
    expected_titles: list[str],
    expected_total: int,
) -> None:
    from api.routers import ai as ai_router

    def fake_generate_search_plan(value, *, allowed_genres, allowed_moods, client=None):
        assert value == query
        return plan

    monkeypatch.setattr(ai_router, "generate_search_plan", fake_generate_search_plan)

    response = client.post("/api/ai/search", json={"query": query})
    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == expected_total
    assert payload["plan"]["order_by"] == plan.order_by
    assert payload["explanation"]

    titles = [item["title"] for item in payload["items"]]
    assert titles[: len(expected_titles)] == expected_titles


def test_ai_search_normalizes_decade_and_runtime() -> None:
    from api.services import ai_search as ai_service

    plan = SearchPlan()
    normalized = ai_service.apply_query_normalization(
        plan,
        query="90s under 90 minutes",
        allowed_genres=["Family"],
        allowed_moods=["Scary"],
    )

    assert normalized.year_min == 1990
    assert normalized.year_max == 1999
    assert normalized.runtime_max == 90


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_message"),
    [
        (
            AiSearchProviderUnavailable("LLM_API_KEY is not configured"),
            503,
            "AI search is temporarily unavailable.",
        ),
        (
            AiSearchError("LLM request failed: connection reset"),
            502,
            "AI search could not be completed. Please try again.",
        ),
    ],
)
def test_ai_search_hides_provider_error_details(
    client: TestClient,
    monkeypatch,
    error: Exception,
    expected_status: int,
    expected_message: str,
) -> None:
    from api.routers import ai as ai_router

    def fail_generate_search_plan(*args, **kwargs):
        raise error

    monkeypatch.setattr(ai_router, "generate_search_plan", fail_generate_search_plan)

    response = client.post("/api/ai/search", json={"query": "moody sci-fi"})

    assert response.status_code == expected_status
    assert response.json()["message"] == expected_message
    assert "LLM" not in response.json()["message"]
