import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.deps import auth as auth_deps
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.routers import ai as ai_router
from api.routers import assistant as assistant_router
from api.routers import movies as movies_router
from api.routers import search as search_router
from api.routers.ui import grid as grid_router
from api.routers.ui import manual_add as manual_add_router
from api.routers.ui import review as review_router
from api.schemas.ai_search import SearchPlan
from api.schemas.llm_filters import LlmMovieFilters
from api.services.assistant import AssistantTemplate


PROVIDER_ENDPOINTS = ("ai", "llm", "semantic", "assistant")


def _install_provider_spy(monkeypatch, endpoint: str) -> list[str]:
    calls: list[str] = []

    if endpoint == "ai":

        def fake_generate_search_plan(query, *, allowed_genres, allowed_moods):
            calls.append(query)
            return SearchPlan()

        monkeypatch.setattr(ai_router, "generate_search_plan", fake_generate_search_plan)
    elif endpoint == "llm":

        def fake_generate_llm_filters(query, *, allowed_genres, allowed_moods):
            calls.append(query)
            return LlmMovieFilters()

        monkeypatch.setattr(movies_router, "generate_llm_filters", fake_generate_llm_filters)
    elif endpoint == "semantic":

        def fake_semantic_search_movies(db, *, query, **kwargs):
            calls.append(query)
            return [], 0

        monkeypatch.setattr(search_router, "semantic_search_enabled", lambda db: True)
        monkeypatch.setattr(
            search_router,
            "semantic_search_movies",
            fake_semantic_search_movies,
        )
    elif endpoint == "assistant":

        def fake_generate_assistant_template(query, *, movies):
            calls.append(query)
            return AssistantTemplate(
                template="Try {{movie_1}}.",
                pick_count=1,
                followup="Enjoy the show.",
            )

        monkeypatch.setattr(
            assistant_router,
            "generate_assistant_template",
            fake_generate_assistant_template,
        )
        monkeypatch.setattr(settings, "assistant_access_token", "assistant-token")
    else:  # pragma: no cover - protected by the fixed parameter list
        raise AssertionError(f"Unknown provider endpoint: {endpoint}")

    return calls


def _request_for(endpoint: str) -> tuple[str, dict[str, object]]:
    if endpoint == "ai":
        return "/api/ai/search", {"query": "sci-fi"}
    if endpoint == "llm":
        return "/movies/search/llm", {"query": "sci-fi"}
    if endpoint == "semantic":
        return "/api/search/semantic", {"query": "Matrix"}
    if endpoint == "assistant":
        return "/api/assistant", {"query": "sci-fi", "limit": 3}
    raise AssertionError(f"Unknown provider endpoint: {endpoint}")


def _install_manual_lookup_spy(monkeypatch) -> list[tuple[str, int | None]]:
    calls: list[tuple[str, int | None]] = []

    def fake_lookup_movie(title: str, year: int | None):
        calls.append((title, year))
        return {"title": title, "year": year}

    monkeypatch.setattr(manual_add_router, "lookup_movie", fake_lookup_movie)
    monkeypatch.setattr(
        manual_add_router,
        "append_movie_to_cleaned_csv",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        manual_add_router,
        "append_movie_to_enriched_csv",
        lambda *args, **kwargs: True,
    )
    return calls


def _install_flag_match_provider_spies(monkeypatch) -> tuple[list[str], list[str]]:
    tmdb_calls: list[str] = []
    omdb_calls: list[str] = []

    def fake_tmdb_lookup(title: str, year: int | None, limit: int):
        tmdb_calls.append(title)
        return [
            {
                "title": title,
                "year": year or 1982,
                "tmdb_id": 900_100,
                "source": "tmdb",
                "match_confidence": 1.0,
            }
        ]

    def fake_omdb_lookup(title: str, year: int | None, limit: int):
        omdb_calls.append(title)
        return []

    monkeypatch.setattr(review_router, "lookup_movie_candidates", fake_tmdb_lookup)
    monkeypatch.setattr(review_router, "lookup_omdb_candidates", fake_omdb_lookup)
    return tmdb_calls, omdb_calls


def _flag_movie_for_match(db_session) -> Movie:
    movie = db_session.get(Movie, 1)
    movie.imdb_id = None
    movie.tmdb_id = None
    movie.flag = MovieFlag(reason="Human review", notes="Provider budget test")
    db_session.commit()
    return movie


@pytest.mark.parametrize("endpoint", PROVIDER_ENDPOINTS)
def test_provider_work_rejects_cross_origin_before_provider_call(
    client: TestClient,
    login_profile,
    monkeypatch,
    endpoint: str,
) -> None:
    calls = _install_provider_spy(monkeypatch, endpoint)
    path, payload = _request_for(endpoint)
    login_profile(1)

    response = client.post(
        path,
        json=payload,
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize("endpoint", PROVIDER_ENDPOINTS)
def test_provider_work_allows_ten_per_minute_then_rejects_without_provider_call(
    client: TestClient,
    login_profile,
    monkeypatch,
    endpoint: str,
) -> None:
    calls = _install_provider_spy(monkeypatch, endpoint)
    path, payload = _request_for(endpoint)
    login_profile(1)
    request_times = iter([1000.0] * 10 + [1059.999, 1060.001])
    monkeypatch.setattr(auth_deps, "monotonic", lambda: next(request_times))

    responses = []
    call_counts = []
    for _ in range(12):
        responses.append(
            client.post(
                path,
                json=payload,
                headers={"Origin": "http://testserver"},
            )
        )
        call_counts.append(len(calls))

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429
    assert responses[11].status_code == 200
    assert call_counts[9:] == [10, 10, 11]


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/ui/movies/manual-add/preview", {"title": "Preview Rejected", "year": 2026}),
        ("/ui/movies/manual-add", {"title": "Create Rejected", "year": 2026}),
    ],
)
def test_manual_add_provider_work_rejects_cross_origin_before_lookup(
    client: TestClient,
    login_profile,
    monkeypatch,
    path: str,
    payload: dict[str, object],
) -> None:
    calls = _install_manual_lookup_spy(monkeypatch)
    login_profile(1)

    response = client.post(
        path,
        json=payload,
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert calls == []


def test_manual_add_lookup_budget_is_shared_by_preview_and_lookup_backed_create(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    calls = _install_manual_lookup_spy(monkeypatch)
    login_profile(1)
    request_times = iter([1000.0] * 10 + [1059.999, 1060.001])
    monkeypatch.setattr(auth_deps, "monotonic", lambda: next(request_times))
    headers = {"Origin": "http://testserver"}

    previews = [
        client.post(
            "/ui/movies/manual-add/preview",
            json={"title": "Budget Preview", "year": 2026},
            headers=headers,
        )
        for _ in range(10)
    ]
    blocked = client.post(
        "/ui/movies/manual-add",
        json={"title": "Budget Create", "year": 2026},
        headers=headers,
    )
    calls_after_rejection = len(calls)
    allowed_after_window = client.post(
        "/ui/movies/manual-add",
        json={"title": "Budget Create", "year": 2026},
        headers=headers,
    )

    assert [response.status_code for response in previews] == [200] * 10
    assert blocked.status_code == 429
    assert calls_after_rejection == 10
    assert allowed_after_window.status_code == 201
    assert len(calls) == 11


def test_manual_add_with_supplied_metadata_does_not_spend_provider_budget(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    calls = _install_manual_lookup_spy(monkeypatch)
    login_profile(1)
    monkeypatch.setattr(auth_deps, "monotonic", lambda: 1000.0)
    headers = {"Origin": "http://testserver"}

    previews = [
        client.post(
            "/ui/movies/manual-add/preview",
            json={"title": "Metadata Budget Preview", "year": 2026},
            headers=headers,
        )
        for _ in range(10)
    ]
    created = client.post(
        "/ui/movies/manual-add",
        json={"title": "Metadata Supplied", "year": 2026, "metadata": {}},
        headers=headers,
    )

    assert [response.status_code for response in previews] == [200] * 10
    assert created.status_code == 201
    assert len(calls) == 10


def test_flag_match_get_preserves_originless_navigation_and_uses_budget(
    client: TestClient,
    db_session,
    login_profile,
    monkeypatch,
) -> None:
    movie = _flag_movie_for_match(db_session)
    tmdb_calls, omdb_calls = _install_flag_match_provider_spies(monkeypatch)
    login_profile(1)

    response = client.get(
        f"/ui/movies/health/review/{movie.id}/matches",
        params={"title": "Blade Runner", "year": 1982},
    )

    assert response.status_code == 200
    assert tmdb_calls == ["Blade Runner"]
    assert omdb_calls == ["Blade Runner"]


def test_flag_match_apply_rejects_cross_origin_before_provider_lookup(
    client: TestClient,
    db_session,
    login_profile,
    monkeypatch,
) -> None:
    movie = _flag_movie_for_match(db_session)
    tmdb_calls, omdb_calls = _install_flag_match_provider_spies(monkeypatch)
    login_profile(1)

    response = client.post(
        f"/ui/movies/health/review/{movie.id}/matches/apply",
        json={
            "title": "Blade Runner",
            "year": 1982,
            "source": "tmdb",
            "tmdb_id": 900_100,
        },
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert tmdb_calls == []
    assert omdb_calls == []


def test_flag_match_budget_is_shared_by_get_and_apply_without_rejected_provider_call(
    client: TestClient,
    db_session,
    login_profile,
    monkeypatch,
) -> None:
    movie = _flag_movie_for_match(db_session)
    tmdb_calls, omdb_calls = _install_flag_match_provider_spies(monkeypatch)
    login_profile(1)
    request_times = iter([1000.0] * 10 + [1059.999, 1060.001])
    monkeypatch.setattr(auth_deps, "monotonic", lambda: next(request_times))
    path = f"/ui/movies/health/review/{movie.id}/matches"
    headers = {"Origin": "http://testserver"}

    searches = [client.get(path, params={"title": "Blade Runner", "year": 1982}) for _ in range(10)]
    apply_path = f"{path}/apply"
    selection = {
        "title": "Blade Runner",
        "year": 1982,
        "source": "tmdb",
        "tmdb_id": 900_100,
    }
    blocked = client.post(apply_path, json=selection, headers=headers)
    calls_after_rejection = (len(tmdb_calls), len(omdb_calls))
    allowed_after_window = client.post(apply_path, json=selection, headers=headers)

    assert [response.status_code for response in searches] == [200] * 10
    assert blocked.status_code == 429
    assert calls_after_rejection == (10, 10)
    assert allowed_after_window.status_code == 200
    assert (len(tmdb_calls), len(omdb_calls)) == (11, 11)


def test_semantic_library_search_allows_ten_then_rejects_before_provider_call(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_semantic_search_movies(db, *, query, **kwargs):
        calls.append(query)
        movie = db.query(Movie).filter(Movie.title == "The Matrix").one()
        return [(movie, 0.1)], 1

    login_profile(1)
    monkeypatch.setattr(grid_router, "semantic_search_enabled", lambda db: True)
    monkeypatch.setattr(
        grid_router,
        "semantic_search_movies",
        fake_semantic_search_movies,
    )
    request_times = iter([1000.0] * 10 + [1059.999, 1060.001])
    monkeypatch.setattr(auth_deps, "monotonic", lambda: next(request_times))
    path = "/ui/movies?q=Matrix&semantic=1"

    responses = [client.get(path) for _ in range(12)]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429
    assert responses[11].status_code == 200
    assert len(calls) == 11


def test_library_requests_without_enabled_semantic_work_do_not_spend_budget(
    client: TestClient,
    login_profile,
    monkeypatch,
) -> None:
    budget_calls: list[str] = []
    provider_calls: list[str] = []

    def record_budget(request, *, scope):
        budget_calls.append(scope)

    def record_provider(db, *, query, **kwargs):
        provider_calls.append(query)
        return [], 0

    login_profile(1)
    monkeypatch.setattr(grid_router, "require_provider_work_budget", record_budget)
    monkeypatch.setattr(grid_router, "semantic_search_movies", record_provider)

    nonsemantic = client.get("/ui/movies?q=Matrix")
    monkeypatch.setattr(grid_router, "semantic_search_enabled", lambda db: False)
    disabled = client.get("/ui/movies?q=Matrix&semantic=1")

    assert nonsemantic.status_code == 200
    assert disabled.status_code == 200
    assert budget_calls == []
    assert provider_calls == []
