from fastapi.testclient import TestClient

from api.schemas.llm_filters import LlmMovieFilters


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
