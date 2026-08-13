from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from api.services import semantic_search
from api.services.semantic_search import (
    SemanticSearchError,
    apply_semantic_query_overrides,
    parse_semantic_intent,
    semantic_query_forces_animation,
)
from core.movie_filters import MovieFilterParams, apply_filters


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


def _mock_embeddings_response(monkeypatch, payload: object) -> None:
    response = SimpleNamespace(status_code=200, json=lambda: payload)
    monkeypatch.setattr(semantic_search.httpx, "post", lambda *args, **kwargs: response)
    monkeypatch.setattr(semantic_search.settings, "llm_api_key", "test-key")
    monkeypatch.setattr(semantic_search.settings, "llm_embedding_dim", 3)


def test_fetch_embeddings_rejects_invalid_json(monkeypatch) -> None:
    sentinel = "SENTINEL_INVALID_EMBEDDINGS_BODY"

    def invalid_json():
        raise ValueError(sentinel)

    response = SimpleNamespace(status_code=200, json=invalid_json)
    monkeypatch.setattr(semantic_search.httpx, "post", lambda *args, **kwargs: response)
    monkeypatch.setattr(semantic_search.settings, "llm_api_key", "test-key")

    with pytest.raises(SemanticSearchError) as error_info:
        semantic_search._fetch_embeddings(["one"])

    assert error_info.value.__cause__ is None
    assert error_info.value.__context__ is None
    assert sentinel not in str(error_info.value)


def test_fetch_embeddings_restores_provider_index_order(monkeypatch) -> None:
    _mock_embeddings_response(
        monkeypatch,
        {
            "data": [
                {"index": 1, "embedding": [4, 5.0, 6]},
                {"index": 0, "embedding": [1, 2.0, 3]},
            ]
        },
    )

    assert semantic_search._fetch_embeddings(["first", "second"]) == [
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ]


@pytest.mark.parametrize(
    ("texts", "payload"),
    [
        (["one"], []),
        (["one"], {}),
        (["one"], {"data": []}),
        (["one", "two"], {"data": [{"index": 0, "embedding": [1, 2, 3]}]}),
        (
            ["one"],
            {
                "data": [
                    {"index": 0, "embedding": [1, 2, 3]},
                    {"index": 1, "embedding": [4, 5, 6]},
                ]
            },
        ),
        (
            ["one", "two"],
            {
                "data": [
                    {"index": 0, "embedding": [1, 2, 3]},
                    {"index": 0, "embedding": [4, 5, 6]},
                ]
            },
        ),
        (["one"], {"data": [{"index": 1, "embedding": [1, 2, 3]}]}),
        (["one"], {"data": [{"index": "0", "embedding": [1, 2, 3]}]}),
        (["one"], {"data": [{"index": True, "embedding": [1, 2, 3]}]}),
        (["one"], {"data": ["not-an-item"]}),
        (["one"], {"data": [{"index": 0, "embedding": "not-a-vector"}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, 2]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, "two", 3]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, float("nan"), 3]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, float("inf"), 3]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, float("-inf"), 3]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, 10**400, 3]}]}),
        (["one"], {"data": [{"index": 0, "embedding": [1, True, 3]}]}),
    ],
)
def test_fetch_embeddings_rejects_malformed_provider_vectors(
    monkeypatch,
    texts,
    payload,
) -> None:
    _mock_embeddings_response(monkeypatch, payload)

    with pytest.raises(SemanticSearchError):
        semantic_search._fetch_embeddings(texts)


def test_query_embedding_replaces_invalid_cached_vector(monkeypatch) -> None:
    monkeypatch.setattr(semantic_search.settings, "llm_embedding_dim", 3)
    monkeypatch.setattr(
        semantic_search,
        "_cache_get",
        lambda db, key: {"embedding": [1.0, 2.0]},
    )
    monkeypatch.setattr(
        semantic_search,
        "_fetch_embeddings",
        lambda texts: [[3.0, 4.0, 5.0]],
    )
    cached_values = []
    monkeypatch.setattr(
        semantic_search,
        "_cache_set",
        lambda db, key, value, ttl: cached_values.append(value),
    )

    embedding = semantic_search.get_query_embedding(SimpleNamespace(), "some query")

    assert embedding == [3.0, 4.0, 5.0]
    assert cached_values == [
        {
            "embedding": [3.0, 4.0, 5.0],
            "model": semantic_search.settings.llm_embedding_model,
        }
    ]


def test_semantic_candidate_query_filters_before_top_k(db_session) -> None:
    params = MovieFilterParams(q=None, year_min=2000, genres=("Drama",))

    query = semantic_search._build_semantic_candidate_query(
        db_session,
        embedding=[0.0] * semantic_search.settings.llm_embedding_dim,
        filtered_query=lambda queryset: apply_filters(queryset, params),
        limit=2,
    )
    sql = str(query.statement.compile(dialect=postgresql.dialect()))

    where_position = sql.index("WHERE")
    order_position = sql.index("ORDER BY")
    limit_position = sql.index("LIMIT")
    assert where_position < order_position < limit_position
    assert "movies.year >=" in sql
    assert "EXISTS" in sql
    assert "movie_documents.embedding <->" in sql
    assert "movies.id ASC" in sql
    assert "movies.id IN" not in sql


def test_filtered_result_outside_global_top_k_is_not_discarded(monkeypatch) -> None:
    movies = [
        SimpleNamespace(id=1, year=1990, genres=[], moods=[]),
        SimpleNamespace(id=2, year=1991, genres=[], moods=[]),
        SimpleNamespace(id=3, year=2001, genres=[], moods=[]),
        SimpleNamespace(id=4, year=2002, genres=[], moods=[]),
        SimpleNamespace(id=5, year=2003, genres=[], moods=[]),
    ]
    ranked_rows = list(zip(movies, (0.01, 0.02, 0.03, 0.03, 0.04), strict=True))
    events = []

    class FakeQuery:
        candidate_limit = None

        def predicate(self, movie):
            return True

        def join(self, *args):
            events.append("join")
            return self

        def order_by(self, *args):
            events.append("order_by")
            return self

        def limit(self, value):
            events.append("limit")
            self.candidate_limit = value
            return self

        def options(self, *args):
            events.append("options")
            return self

        def all(self):
            events.append("all")
            rows = [row for row in ranked_rows if self.predicate(row[0])]
            rows.sort(key=lambda row: (row[1], row[0].id))
            return rows[: self.candidate_limit]

    fake_query = FakeQuery()

    class FakeSession:
        def query(self, *args):
            events.append("query")
            return fake_query

    def apply_structural_filter(queryset):
        events.append("filter")
        assert queryset.candidate_limit is None
        queryset.predicate = lambda movie: movie.year >= 2000
        return queryset

    monkeypatch.setattr(semantic_search, "semantic_search_enabled", lambda db: True)
    monkeypatch.setattr(semantic_search, "get_query_embedding", lambda db, query: [0.0])

    rows, total = semantic_search.semantic_search_movies(
        FakeSession(),
        query="filtered query",
        filtered_query=apply_structural_filter,
        limit=2,
        page=1,
        page_size=2,
    )

    assert [movie.id for movie, _ in rows] == [3, 4]
    assert total == 2
    assert events == ["query", "join", "filter", "order_by", "limit", "options", "all"]
