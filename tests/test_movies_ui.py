from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.movie_review import MovieReviewCheck
from api.models.person import Person, Role, RoleType
from api.services import movies_curated
from api.services.movie_review import (
    apply_all_title_year_corrections,
    detect_review_issues,
    get_review_queue,
)
from api.services.profiles import get_profiles
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH, dump_filter_cookie


def test_movies_grid_persists_filters_via_cookie(client: TestClient) -> None:
    first = client.get(
        "/ui/movies",
        params={
            "genres": "Science Fiction",
            "order_by": "runtime_asc",
        },
    )
    assert first.status_code == 200
    assert client.cookies.get(FILTER_COOKIE_NAME) is not None

    second = client.get("/ui/movies")
    assert second.status_code == 200
    html = second.text
    assert 'id="genres-input" value="Science Fiction"' in html
    assert 'data-clear-filter="genre" data-filter-value="Science Fiction"' in html
    assert 'option value="runtime_asc" selected' in html
    assert "Blade Runner" in html
    assert "Toy Story" not in html


def test_movies_grid_explicit_clear_removes_cookie_backed_preset(
    client: TestClient,
) -> None:
    selected = client.get("/ui/movies", params={"preset": "hidden-gems"})
    assert selected.status_code == 200

    restored = client.get("/ui/movies")
    assert 'id="preset-input" value="hidden-gems"' in restored.text
    assert 'data-clear-filter="preset"' in restored.text

    cleared = client.get("/ui/movies", params={"_filters": "1", "page": "1"})
    assert cleared.status_code == 200
    assert 'id="preset-input" value=""' in cleared.text
    assert 'data-clear-filter="preset"' not in cleared.text

    restored_after_clear = client.get("/ui/movies")
    assert 'id="preset-input" value=""' in restored_after_clear.text
    assert 'data-clear-filter="preset"' not in restored_after_clear.text


def test_movies_grid_ignores_invalid_cookie_backed_filters(client: TestClient) -> None:
    client.cookies.set(
        FILTER_COOKIE_NAME,
        dump_filter_cookie(
            {
                "year_min": "not-a-year",
                "order_by": "sideways",
                "preset": "hidden-gems",
                "page": 4,
            }
        ),
        domain="testserver",
        path=FILTER_COOKIE_PATH,
    )

    response = client.get("/ui/movies")

    assert response.status_code == 200
    html = response.text
    assert 'id="preset-input" value=""' in html
    assert 'id="year-min-input" value=""' in html
    assert 'option value="title_asc" selected' in html
    assert "Blade Runner" in html


def test_movies_grid_rejects_invalid_explicit_filters(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"order_by": "sideways"})

    assert response.status_code == 400


def test_movies_grid_view_switch_preserves_cookie_backed_filters(client: TestClient) -> None:
    selected = client.get(
        "/ui/movies",
        params={"genres": "Science Fiction", "order_by": "runtime_asc"},
    )
    assert selected.status_code == 200

    switched = client.get("/ui/movies", params={"view": "list"})
    assert switched.status_code == 200
    html = switched.text
    assert 'id="genres-input" value="Science Fiction"' in html
    assert 'option value="runtime_asc" selected' in html
    assert 'input type="hidden" name="view" value="list"' in html
    assert "Blade Runner" in html
    assert "Toy Story" not in html


def test_movies_list_view_renders_modern_list_rows(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"view": "list"})

    assert response.status_code == 200
    html = response.text
    assert "data-results-table" in html
    assert 'id="results-table-table"' in html
    assert "data-results-grid" not in html
    assert 'class="library-list-movie"' in html
    assert 'class="library-list-id"' not in html
    assert 'data-label="Vault ID"' not in html
    assert 'class="library-list-meta"' in html
    assert "data-preference-button" in html
    assert "data-table-sort" in html


def test_movies_list_view_title_sort_sets_aria_sort(client: TestClient) -> None:
    ascending = client.get(
        "/ui/movies",
        params={"view": "list", "order_by": "title_asc"},
    )
    descending = client.get(
        "/ui/movies",
        params={"view": "list", "order_by": "title_desc"},
    )

    assert ascending.status_code == 200
    assert '<th scope="col" aria-sort="ascending">' in ascending.text
    assert '<th scope="col" aria-sort="descending">' in descending.text


def test_movies_list_view_vault_id_sort_does_not_render_vault_id_column(
    client: TestClient,
) -> None:
    response = client.get(
        "/ui/movies",
        params={"view": "list", "order_by": "id_asc"},
    )

    assert response.status_code == 200
    assert 'data-label="Vault ID"' not in response.text
    assert 'class="library-list-id"' not in response.text
    assert "Vault ID ↑" in response.text


def test_movies_sort_dropdown_includes_random_option(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"view": "list", "order_by": "random"})

    assert response.status_code == 200
    assert '<option value="random" selected>Random</option>' in response.text


def test_movies_grid_filters_by_mood(client: TestClient) -> None:
    response = client.get("/ui/movies", params={"moods": "Moody"})
    assert response.status_code == 200
    html = response.text
    assert "<h3>Moods</h3>" in html
    assert 'data-filter-group="moods"' in html
    assert 'data-filter-value="Atmospheric">Atmospheric</button>' in html
    assert 'data-filter-value="High-energy">High-energy</button>' in html
    assert 'id="moods-input" value="Atmospheric"' in html
    assert 'data-clear-filter="mood" data-filter-value="Atmospheric"' in html
    assert "Blade Runner" in html
    assert "The Matrix" not in html


def test_library_card_can_be_flagged_for_review(client: TestClient, db_session) -> None:
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()

    page = client.get("/ui/movies")
    assert "data-review-flag-button" in page.text
    assert "js/card_review_flag.js?v=" in page.text

    response = client.post(f"/ui/movies/{movie.id}/review-flag")
    assert response.status_code == 200
    assert response.json() == {"movie_id": movie.id, "flagged": True}

    db_session.expire_all()
    flag = db_session.get(MovieFlag, movie.id)
    assert flag is not None
    assert flag.reason == "Human review"
    assert flag.notes == "Flagged for review"

    repeated = client.post(f"/ui/movies/{movie.id}/review-flag")
    assert repeated.status_code == 200
    assert db_session.query(MovieFlag).filter(MovieFlag.movie_id == movie.id).count() == 1


def test_library_review_flag_rejects_unknown_movie(client: TestClient) -> None:
    response = client.post("/ui/movies/999999/review-flag")
    assert response.status_code == 404


def test_movie_detail_flag_can_be_managed_without_admin_token(
    client: TestClient, db_session
) -> None:
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()

    create = client.put(
        f"/ui/movies/{movie.id}/flag",
        json={
            "reason": "Wrong runtime/year",
            "notes": "Runtime appears to be from another release.",
        },
    )
    assert create.status_code == 200
    assert create.json()["reason"] == "Wrong runtime/year"
    assert create.json()["notes"] == "Runtime appears to be from another release."

    page = client.get(f"/ui/movies/{movie.id}")
    assert page.status_code == 200
    assert "Needs review" in page.text
    assert "Wrong runtime/year" in page.text
    assert "Runtime appears to be from another release." in page.text
    assert "Manage flag" in page.text

    resolve = client.delete(f"/ui/movies/{movie.id}/flag")
    assert resolve.status_code == 204
    db_session.expire_all()
    assert db_session.get(MovieFlag, movie.id) is None


def test_movie_detail_flag_rejects_unexpected_input(client: TestClient) -> None:
    response = client.put(
        "/ui/movies/1/flag",
        json={
            "reason": "Metadata cleanup",
            "notes": "Check title",
            "admin_token": "not accepted",
        },
    )
    assert response.status_code == 422


def test_reviewer_can_report_movie_but_cannot_manage_flags(
    client: TestClient,
    db_session,
    login_profile,
) -> None:
    login_profile(2)

    detail = client.get("/ui/movies/1")
    assert detail.status_code == 200
    assert "Report issue" in detail.text
    assert "Manage flag" not in detail.text
    assert "data-edit-button" not in detail.text

    report = client.post(
        "/movies/1/flag/report",
        json={"reason": "Wrong runtime/year", "notes": "Runtime looks off."},
        headers={"Origin": "http://testserver"},
    )
    assert report.status_code == 200
    body = report.json()
    assert body["movie_id"] == 1
    assert body["reported_by_profile_id"] == 2

    db_session.expire_all()
    flag = db_session.get(MovieFlag, 1)
    assert flag is not None
    assert flag.reason == "Wrong runtime/year"
    assert flag.notes == "Runtime looks off."
    assert flag.reported_by_profile_id == 2

    overwrite = client.put(
        "/ui/movies/1/flag",
        json={"reason": "Other", "notes": "Reviewer should not manage."},
        headers={"Origin": "http://testserver"},
    )
    assert overwrite.status_code == 403

    resolve = client.delete(
        "/ui/movies/1/flag",
        headers={"Origin": "http://testserver"},
    )
    assert resolve.status_code == 403

    db_session.expire_all()
    flag = db_session.get(MovieFlag, 1)
    assert flag is not None
    assert flag.reason == "Wrong runtime/year"


def test_reviewer_report_does_not_overwrite_existing_admin_flag(
    client: TestClient,
    db_session,
    login_profile,
) -> None:
    db_session.add(
        MovieFlag(
            movie_id=1,
            reason="Movie mismatch",
            notes="Admin context stays.",
        )
    )
    db_session.commit()

    login_profile(2)

    response = client.post(
        "/movies/1/flag/report",
        json={"reason": "Other", "notes": "Reviewer context."},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert response.json()["reported_by_profile_id"] == 2

    db_session.expire_all()
    flag = db_session.get(MovieFlag, 1)
    assert flag is not None
    assert flag.reason == "Movie mismatch"
    assert flag.notes == "Admin context stays."
    assert flag.reported_by_profile_id == 2


def test_reviewer_report_requires_same_origin(
    client: TestClient,
    login_profile,
) -> None:
    login_profile(2)

    payload = {"reason": "Wrong runtime/year", "notes": "Runtime looks off."}
    missing_origin = client.post("/movies/1/flag/report", json=payload)
    cross_origin = client.post(
        "/movies/1/flag/report",
        json=payload,
        headers={"Origin": "http://evil.test"},
    )
    same_origin = client.post(
        "/movies/1/flag/report",
        json=payload,
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403
    assert same_origin.status_code == 200


def test_admin_can_manage_movie_detail_flags_with_session(
    client: TestClient,
    db_session,
    login_profile,
) -> None:
    login_profile(1)

    detail = client.get("/ui/movies/1")
    assert detail.status_code == 200
    assert 'data-flag-mode="manage"' in detail.text
    assert "data-edit-button" in detail.text

    create = client.put(
        "/ui/movies/1/flag",
        json={"reason": "Metadata cleanup", "notes": "Admin note."},
        headers={"Origin": "http://testserver"},
    )
    assert create.status_code == 200
    assert create.json()["reason"] == "Metadata cleanup"

    resolve = client.delete(
        "/ui/movies/1/flag",
        headers={"Origin": "http://testserver"},
    )
    assert resolve.status_code == 204

    db_session.expire_all()
    assert db_session.get(MovieFlag, 1) is None


def test_reviewer_cannot_open_admin_health_or_review_routes(
    client: TestClient,
    login_profile,
) -> None:
    login_profile(2)

    library = client.get("/ui/movies")
    assert library.status_code == 200
    assert "Vault Health" not in library.text

    for path in (
        "/ui/movies/health",
        "/ui/movies/health/missing",
        "/ui/flags",
        "/ui/review",
        "/ui/source-sync",
        "/ui/first-import",
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 403


def test_admin_compatibility_routes_redirect_to_health_workbench(client: TestClient) -> None:
    expected_locations = {
        "/ui/flags": "/ui/movies/health?view=flags#review-workbench",
        "/ui/review": "/ui/movies/health#review-workbench",
        "/ui/source-sync": "/ui/movies/health#source-synchronization",
    }

    for path, location in expected_locations.items():
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == location


def test_empty_library_shows_admin_first_import_cta(
    client: TestClient,
    db_session,
) -> None:
    for movie in db_session.query(Movie).all():
        db_session.delete(movie)
    db_session.commit()

    page = client.get("/ui/movies")

    assert page.status_code == 200
    assert "Your library is empty" in page.text
    assert 'href="/ui/first-import"' in page.text
    assert "Nothing matched these filters." not in page.text
    assert 'href="/ui/movies">Clear all</a>' not in page.text


def test_empty_library_hides_first_import_cta_for_reviewer(
    client: TestClient,
    db_session,
    login_profile,
) -> None:
    login_profile(2)
    for movie in db_session.query(Movie).all():
        db_session.delete(movie)
    db_session.commit()

    page = client.get("/ui/movies")

    assert page.status_code == 200
    assert "Your library is empty" in page.text
    assert 'href="/ui/first-import"' not in page.text


def test_filtered_empty_library_state_still_offers_clear_all(client: TestClient) -> None:
    page = client.get("/ui/movies", params={"q": "not-in-the-vault"})

    assert page.status_code == 200
    assert "Nothing matched these filters." in page.text
    assert 'href="/ui/movies">Clear all</a>' in page.text
    assert 'href="/ui/first-import"' not in page.text


def test_first_import_page_reuses_source_sync_upload_flow(client: TestClient) -> None:
    page = client.get("/ui/first-import")

    assert page.status_code == 200
    assert "<h1>First import</h1>" in page.text
    assert (
        'method="post" action="/ui/first-import/upload" enctype="multipart/form-data"' in page.text
    )
    assert 'name="source_file"' in page.text
    assert (
        'accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"'
        in page.text
    )
    assert "Preview import" in page.text


def test_movies_grid_paginates_in_complete_36_card_pages(client: TestClient, db_session) -> None:
    for index in range(10):
        db_session.add(
            Movie(
                title=f"Pagination Movie {index:02d}",
                year=2020,
                runtime=100,
                imdb_id=f"ttpagination{index:02d}",
                tmdb_id=9000 + index,
            )
        )
    db_session.commit()

    first_page = client.get("/ui/movies", params={"page": 1, "view": "grid"})
    second_page = client.get("/ui/movies", params={"page": 2, "view": "grid"})

    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert first_page.text.count("data-movie-card") == 36
    assert second_page.text.count("data-movie-card") == 7
    assert "Page 1 of 2" in first_page.text
    assert "Page 2 of 2" in second_page.text
    assert "page=0" not in first_page.text
    assert 'data-disabled="true"' in first_page.text
    assert 'data-goto-page="1"' in first_page.text
    assert 'data-goto-page="1"' in second_page.text
    assert 'data-disabled="true"' in second_page.text


def test_library_search_is_prominent_and_searches_identity_fields(
    client: TestClient, db_session
) -> None:
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()
    movie.vault_id = "V0001"
    director = Person(name="Ridley Scott")
    db_session.add(director)
    db_session.flush()
    db_session.add(
        Role(
            movie_id=movie.id,
            person_id=director.id,
            role_type=RoleType.DIRECTOR,
        )
    )
    db_session.commit()

    page = client.get("/ui/movies")

    assert page.text.count("<main ") == 1
    assert '<main id="main" class="app-main">' in page.text
    assert '<main class="library-shell page-shell"' not in page.text
    assert '<div class="library-shell page-shell" id="results" data-results-shell>' in page.text
    assert '<section class="library-search-panel" aria-label="Search your Vault">' in page.text
    assert 'id="library-search-title"' not in page.text
    assert "Find a movie by title" not in page.text
    assert 'placeholder="Try “Ben Stiller” “2010” “Titanic” or a Vault ID"' in page.text
    search_label = page.text.index('<label class="sr-only" for="search-q">')
    search_label_end = page.text.index("</label>", search_label)
    search_input = page.text.index('id="search-q"')
    search_button = page.text.index('id="search-button"')
    assert search_label < search_label_end < search_input < search_button
    assert 'enterkeyhint="search"' in page.text
    assert 'aria-label="Open filters"' in page.text
    assert 'aria-label="Random trusted movie"' in page.text
    assert "data-vault-busy" in page.text
    assert "Vault is thinking" in page.text
    assert 'aria-label="Grid view"' in page.text
    assert 'aria-label="List view"' in page.text
    assert "data-filters-summary" in page.text
    assert 'aria-label="Pending filter selections"' in page.text
    assert "data-filters-reset" in page.text
    assert 'aria-labelledby="filters-dialog-title"' in page.text
    assert 'aria-describedby="filters-dialog-description"' in page.text
    assert '<h2 id="filters-dialog-title">Filters</h2>' in page.text
    assert '<p id="filters-dialog-description">Narrow the collection.</p>' in page.text
    assert 'aria-labelledby="edit-dialog-title"' in page.text
    assert 'aria-describedby="edit-dialog-description"' in page.text
    assert '<h2 id="edit-dialog-title">Edit Movie</h2>' in page.text
    assert '<p id="edit-dialog-description">Update this movie\'s metadata.</p>' in page.text
    assert 'id="year-custom" hidden' in page.text
    assert 'id="runtime-custom" hidden' in page.text
    assert 'id="fliclists"' not in page.text
    assert 'class="chip chip-preset"' not in page.text
    assert "css/movies.css?v=" in page.text
    assert "css/movie_components.css?v=" in page.text
    assert "js/library_page.js?v=" in page.text
    assert "css/base.css?v=" in page.text
    assert '<span class="brand-mark">Vault 966</span>' in page.text
    assert 'class="brand"\n            href="/ui/movies"' in page.text
    assert 'data-nav-toggle\n            aria-expanded="false"' in page.text
    assert 'aria-controls="primary-nav"' in page.text
    assert 'aria-label="Open primary navigation"' in page.text
    assert '<nav\n            class="primary-nav"' in page.text
    assert 'aria-label="Primary navigation"' in page.text
    assert 'role="menubar"' not in page.text
    assert 'role="menuitem"' not in page.text
    assert "Movie dispatch" not in page.text
    assert "js/base.js?v=" in page.text

    by_vault_id = client.get("/ui/movies", params={"q": "V0001"})
    by_year = client.get("/ui/movies", params={"q": "1982"})
    by_person = client.get("/ui/movies", params={"q": "Ridley Scott"})

    assert "Blade Runner" in by_vault_id.text
    assert "Blade Runner" in by_year.text
    assert "Blade Runner" in by_person.text


def test_health_page_uses_vault_health_title_and_prioritizes_metrics(
    client: TestClient,
) -> None:
    response = client.get("/ui/movies/health")

    assert response.status_code == 200
    assert "<h1>Vault Health</h1>" in response.text
    assert 'class="library-heading"' in response.text
    assert "items need" in response.text
    assert "Back to movies" not in response.text
    assert response.text.count('data-vault-busy-message="Checking Vault Health…"') == 2
    assert "Vault dashboard" in response.text
    assert "What changed, what needs decisions, and what is incomplete." in response.text
    assert "Open decisions" in response.text
    assert "New additions" in response.text
    assert "Outdated fields" in response.text
    assert "Metadata maintenance" in response.text
    assert 'href="#metadata-maintenance">Metadata maintenance</a>' in response.text
    assert "Run full metadata maintenance" in response.text
    assert "This does not accept source rows" in response.text
    assert "Preview counts are read-only" in response.text
    assert "Checking API access" in response.text
    assert "data-maintenance-providers" in response.text
    assert 'href="#metadata-maintenance"' in response.text
    assert 'id="metadata-maintenance"' in response.text
    assert "data-maintenance-history" in response.text
    assert 'data-maintenance-latest="genres"' in response.text
    assert 'data-maintenance-latest="posters"' in response.text
    assert "data-update-cancel" in response.text
    assert "Cancel queued maintenance" in response.text
    assert "Normalize genres" in response.text
    assert "Find missing posters" in response.text
    assert "Review workbench" in response.text
    assert 'href="/ui/movies/health/missing"' in response.text
    assert "View missing details" in response.text
    assert "Source synchronization" in response.text
    assert "Add one movie" in response.text
    assert "Add to Vault" in response.text
    assert "data-source-manual-add" in response.text
    assert "js/source_sync_manual_add.js?v=" in response.text
    assert 'href="#metadata-gaps"' not in response.text
    assert 'href="/ui/review"' not in response.text
    assert ">Review</a" not in response.text
    assert "Flic Recommendation" not in response.text


def test_health_page_get_does_not_fetch_recommendation_provider(
    client: TestClient, monkeypatch
) -> None:
    def fail_provider(*args, **kwargs):
        raise AssertionError("GET health must not call the LLM recommendation provider")

    monkeypatch.setattr(movies_curated, "_fetch_recommendation_text", fail_provider)

    response = client.get("/ui/movies/health")

    assert response.status_code == 200
    assert "Vault Health" in response.text


def test_flags_page_lists_flagged_movies(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.post("/movies/1/flag", json={"reason": "Metadata cleanup"}, headers=admin_headers)
    assert resp.status_code == 200

    page = client.get("/ui/movies/health?view=flags")
    assert page.status_code == 200
    html = page.text
    assert "Flags" in html
    assert "Metadata cleanup" in html
    assert "Repair by title match" in html
    assert "data-flag-match-search" in html
    assert 'value="Blade Runner"' in html


def test_flags_queue_shows_reporter_timing_and_reason_filter(
    client: TestClient,
    db_session,
) -> None:
    profiles = get_profiles(db_session)
    reviewer = next(profile for profile in profiles if profile.name == "User B")
    db_session.add(
        MovieFlag(
            movie_id=1,
            reason="Wrong runtime/year",
            notes="Runtime looks off.",
            reported_by_profile_id=reviewer.id,
        )
    )
    db_session.add(MovieFlag(movie_id=2, reason="Poster/backdrop issue"))
    db_session.commit()

    page = client.get(
        "/ui/movies/health",
        params={"view": "flags", "flag_reason": "Wrong runtime/year"},
    )

    assert page.status_code == 200
    html = page.text
    assert "Wrong runtime/year" in html
    assert "Runtime looks off." in html
    assert "Reported by" in html
    assert "User B" in html
    assert "Opened" in html
    assert "Last updated" in html
    assert "Resolve / Dismiss" in html
    assert 'option value="Wrong runtime/year" selected' in html
    assert "Poster/backdrop issue" in html
    assert "The Matrix" not in html


def test_flags_queue_resolve_action_removes_flag_and_preserves_filter(
    client: TestClient,
    db_session,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.vault_id = "V0001"
    db_session.add(
        MovieFlag(
            movie_id=movie.id,
            reason="Wrong runtime/year",
            notes="Runtime looks off.",
        )
    )
    db_session.commit()

    response = client.post(
        f"/ui/movies/health/review/flags/{movie.id}/resolve",
        params={"flag_reason": "Wrong runtime/year"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "view=flags" in response.headers["location"]
    assert "flag_reason=Wrong%20runtime%2Fyear" in response.headers["location"]
    assert "V0001%20removed%20from%20Flags" in response.headers["location"]
    db_session.expire_all()
    assert db_session.get(MovieFlag, movie.id) is None


def test_reviewer_cannot_resolve_flags_from_review_queue(
    client: TestClient,
    db_session,
    login_profile,
) -> None:
    db_session.add(MovieFlag(movie_id=1, reason="Wrong runtime/year"))
    db_session.commit()
    login_profile(2)

    response = client.post(
        "/ui/movies/health/review/flags/1/resolve",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 403
    db_session.expire_all()
    assert db_session.get(MovieFlag, 1) is not None


def test_review_route_redirects_to_vault_health_workbench(client: TestClient) -> None:
    resp = client.get("/ui/movies/review", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/ui/movies/health?view=vault#review-workbench"


def test_review_queue_shows_detected_issue_and_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.title = "Blade Runner (1981)"
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.get("/ui/movies/health")

    assert response.status_code == 200
    assert "Review workbench" in response.text
    assert "Title and year disagree" in response.text
    assert "V0001" in response.text


def test_title_year_authority_updates_year_and_preserves_other_flag_issues(
    db_session,
) -> None:
    first = db_session.get(Movie, 1)
    first.title = "Blade Runner (1981)"
    first.year = 1982
    first.flag = MovieFlag(
        reason="Human review",
        notes="Title and year disagree",
    )
    second = db_session.get(Movie, 2)
    second.title = "The Matrix (2001)"
    second.year = 1999
    second.flag = MovieFlag(
        reason="Human review",
        notes="Title and year disagree; No source IDs",
    )
    db_session.add(
        MovieReviewCheck(
            movie_id=first.id,
            issue_type="title_year_conflict",
            issue_fingerprint=detect_review_issues(first)[0].fingerprint,
            decision="needs_fix",
        )
    )
    db_session.commit()

    result = apply_all_title_year_corrections(db_session, profile_id=1)

    db_session.expire_all()
    assert result.movie_count == 2
    assert result.cleared_flag_count == 1
    assert db_session.get(Movie, 1).year == 1981
    assert db_session.get(Movie, 1).flag is None
    assert db_session.get(Movie, 2).year == 2001
    assert db_session.get(Movie, 2).flag.notes == "No source IDs"
    assert (
        db_session.query(MovieReviewCheck)
        .filter(MovieReviewCheck.movie_id == first.id)
        .one()
        .decision
        == "title_year_applied"
    )


def test_review_checked_removes_movie_from_queue(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post("/ui/movies/health/review/1/checked", follow_redirects=True)

    assert response.status_code == 200
    assert "V0001 marked as checked." in response.text
    assert "Year is missing" not in response.text


def test_vault_review_actions_preserve_vault_category(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/1/checked?view=vault",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "view=vault" in response.headers["location"]


def test_review_needs_fix_creates_flag_with_vault_id(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.year = None
    movie.vault_id = "V0001"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/1/needs-fix",
        follow_redirects=True,
    )
    flags = client.get("/ui/movies/health?view=flags")

    assert response.status_code == 200
    assert "V0001 added to Flags." in response.text
    assert "V0001" in flags.text
    assert "Human review" in flags.text


def test_bulk_review_needs_fix_moves_all_open_checks_to_flags(
    client: TestClient, db_session
) -> None:
    movies = db_session.query(Movie).order_by(Movie.id).limit(2).all()
    for index, movie in enumerate(movies, start=1):
        movie.year = None
        movie.vault_id = f"V{index:04d}"
    db_session.commit()

    response = client.post(
        "/ui/movies/health/review/vault/needs-fix-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Moved%202%20Vault%20checks%20to%20Flags" in response.headers["location"]
    assert get_review_queue(db_session)[0] == []
    flags = db_session.query(MovieFlag).order_by(MovieFlag.movie_id).all()
    assert [flag.movie_id for flag in flags] == [movie.id for movie in movies]
    assert all(flag.reason == "Human review" for flag in flags)
    assert all(flag.notes == "Year is missing" for flag in flags)


def test_movie_detail_shows_review_bar(client: TestClient) -> None:
    resp = client.get("/ui/movies/1", params={"review": "1"})
    assert resp.status_code == 200
    html = resp.text
    assert "Review mode" in html
    assert 'href="/ui/movies/2?review=1"' in html


def test_missing_details_page_renders(client: TestClient) -> None:
    resp = client.get("/ui/movies/health/missing")
    assert resp.status_code == 200
    html = resp.text
    assert "Missing runtime" in html
    assert "Missing synopsis" in html
    assert "Missing artwork" in html
    assert 'href="/ui/movies/health"' in html
    assert html.count('aria-current="page"') >= 1
