import pytest

from api.schemas.ai_search import SearchPlan
from api.services import ai_search as ai_service


@pytest.mark.parametrize(
    "query, expected",
    [
        (
            "scary movies from the 90's",
            {"year_min": 1990, "year_max": 1999, "genres": {"Horror", "Thriller"}},
        ),
        (
            "family movies less than 90 minutes",
            {"runtime_max": 90, "genres": {"Family"}},
        ),
        (
            "space horror like Alien",
            {"genres": {"Science Fiction", "Horror", "Thriller"}},
        ),
        (
            "movies from my 20's",
            {"year_min": None, "year_max": None},
        ),
        (
            "90s classics",
            {"year_min": 1990, "year_max": 1999},
        ),
        (
            "00s family movies",
            {"year_min": 2000, "year_max": 2009, "genres": {"Family"}},
        ),
        (
            "2010s thrillers under 100 minutes",
            {"year_min": 2010, "year_max": 2019, "genres": {"Thriller"}, "runtime_max": 100},
        ),
    ],
)
def test_ai_search_golden_queries(query: str, expected: dict) -> None:
    plan = SearchPlan()
    normalized = ai_service.apply_query_normalization(
        plan,
        query=query,
        allowed_genres=["Family", "Horror", "Thriller", "Science Fiction"],
        allowed_moods=["Scary", "Family"],
    )

    if "year_min" in expected:
        assert normalized.year_min == expected["year_min"]
    if "year_max" in expected:
        assert normalized.year_max == expected["year_max"]
    if "runtime_max" in expected:
        assert normalized.runtime_max == expected["runtime_max"]
    if "genres" in expected:
        assert expected["genres"].issubset(set(normalized.genres))


@pytest.mark.parametrize(
    "query",
    [
        "!!!???",
        "🐙 strange vibes 1970's",
        "Sci-Fi???\n\n\n",
        "scary   ",
        "family & fun",
        "90’s classics",
    ],
)
def test_ai_search_endpoint_handles_odd_input(client, monkeypatch, query: str) -> None:
    from api.routers import ai as ai_router

    def fake_generate_search_plan(value, *, allowed_genres, allowed_moods, client=None):
        return SearchPlan()

    monkeypatch.setattr(ai_router, "generate_search_plan", fake_generate_search_plan)

    response = client.post("/api/ai/search", json={"query": query})
    assert response.status_code == 200
    payload = response.json()
    assert "plan" in payload
    assert "items" in payload
