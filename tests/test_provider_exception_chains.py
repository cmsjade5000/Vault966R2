from collections.abc import Callable, Iterator

import httpx
import pytest

from api.config import settings
from api.services import (
    ai_search,
    assistant,
    llm_filters,
    movie_lookup,
    movie_trailers,
    movies_curated,
    semantic_search,
)


def _exception_graph(root: BaseException) -> Iterator[BaseException]:
    pending = [root]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)


class _FailingClient:
    def __init__(self, sentinel: str) -> None:
        self.sentinel = sentinel

    def post(self, url, *, json, headers):
        request = httpx.Request(
            "POST",
            f"{url}?api_key={self.sentinel}",
            json=json,
            headers=headers,
        )
        raise httpx.RequestError(
            f"connection reset; Authorization: Bearer {self.sentinel}",
            request=request,
        )


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("ai_search", ai_search.AiSearchError),
        ("assistant", assistant.AssistantError),
        ("llm_filters", llm_filters.LlmFilterError),
        ("tmdb_search", movie_lookup.MovieLookupError),
        ("tmdb_detail", movie_lookup.MovieLookupError),
        ("omdb_detail", movie_lookup.MovieLookupError),
        ("omdb_search", movie_lookup.MovieLookupError),
        ("movie_trailers", movie_trailers.MovieTrailerUnavailable),
        ("movies_curated", movies_curated.RecommendationError),
        ("semantic_search", semantic_search.SemanticSearchError),
    ],
)
def test_provider_wrappers_detach_raw_transport_exception_graph(
    monkeypatch,
    case: str,
    expected_error: type[Exception],
) -> None:
    sentinel = f"SENTINEL_{case.upper()}_CONTEXT_SECRET"
    monkeypatch.setattr(settings, "llm_api_key", sentinel)
    monkeypatch.setattr(settings, "tmdb_api_key", sentinel)
    monkeypatch.setattr(settings, "omdb_api_key", sentinel)
    monkeypatch.setattr(semantic_search, "EMBEDDING_MAX_RETRIES", 1)
    monkeypatch.setattr(semantic_search.time, "sleep", lambda _seconds: None)

    def fail_get(url, *, params, timeout):
        request = httpx.Request(
            "GET",
            url,
            params=params,
            headers={"Authorization": f"Bearer {sentinel}"},
        )
        raise httpx.RequestError(
            f"connection reset; Authorization: Bearer {sentinel}",
            request=request,
        )

    def fail_post(url, *, headers, json, timeout):
        request = httpx.Request(
            "POST",
            f"{url}?api_key={sentinel}",
            headers=headers,
            json=json,
        )
        raise httpx.RequestError(
            f"connection reset; Authorization: Bearer {sentinel}",
            request=request,
        )

    monkeypatch.setattr(httpx, "get", fail_get)
    monkeypatch.setattr(httpx, "post", fail_post)
    movie_lookup._tmdb_search_ids.cache_clear()
    movie_lookup._tmdb_movie_detail.cache_clear()
    movie_lookup._omdb_details.cache_clear()

    client = _FailingClient(sentinel)
    calls: dict[str, Callable[[], object]] = {
        "ai_search": lambda: ai_search.generate_search_plan(
            "context sentinel",
            allowed_genres=[],
            allowed_moods=[],
            client=client,
        ),
        "assistant": lambda: assistant.generate_assistant_template(
            "context sentinel", movies=[], client=client
        ),
        "llm_filters": lambda: llm_filters.generate_llm_filters(
            "context sentinel",
            allowed_genres=[],
            allowed_moods=[],
            client=client,
        ),
        "tmdb_search": lambda: movie_lookup._tmdb_search_ids(sentinel, "Context Sentinel", 2000),
        "tmdb_detail": lambda: movie_lookup._tmdb_movie_detail(sentinel, 999991),
        "omdb_detail": lambda: movie_lookup._omdb_details(sentinel, "tt9999991"),
        "omdb_search": lambda: movie_lookup.lookup_omdb_candidates("Context Sentinel"),
        "movie_trailers": lambda: movie_trailers._fetch_tmdb_videos(999991),
        "movies_curated": lambda: movies_curated._fetch_recommendation_text(
            {"kind": "context sentinel"}, client=client
        ),
        "semantic_search": lambda: semantic_search._fetch_embeddings(["context sentinel"]),
    }

    with pytest.raises(expected_error) as error_info:
        calls[case]()

    graph = list(_exception_graph(error_info.value))
    diagnostic = "\n".join(f"{type(error).__name__}: {error}" for error in graph)

    assert all(not isinstance(error, httpx.HTTPError) for error in graph)
    assert sentinel not in diagnostic
    assert "[REDACTED]" in diagnostic
    assert "connection reset" in diagnostic
    if case != "semantic_search":
        assert error_info.value.__cause__ is None
        assert error_info.value.__context__ is None
