from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from api.models.movie import Movie, MovieIngestProvenance
from api.models.source_sync import SourceMovieRow, SourceReconciliationMatch, SourceSnapshot
from api.routers.ui import first_import as first_import_ui
from api.routers.ui.source_sync import _neutralize_spreadsheet_formula
from api.services import source_sync


def _csv(*rows: str) -> bytes:
    header = "Title,Time,Director,Year,Genre,Content Rating,Release Date,HD"
    return ("\n".join((header, *rows)) + "\n").encode()


def _candidate(
    *,
    title: str = "Arrival",
    year: int = 2016,
    runtime: int = 116,
    tmdb_id: int = 329865,
    imdb_id: str = "tt2543164",
    confidence: float = 0.99,
    strategy: str = "exact",
) -> dict:
    return {
        "title": title,
        "year": year,
        "runtime": runtime,
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "genres": ["Science Fiction", "Drama"],
        "poster_url": "https://image.tmdb.org/t/p/w342/example.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w780/example.jpg",
        "overview": "A linguist works to communicate with visitors.",
        "match_confidence": confidence,
        "match_strategy": strategy,
        "source": "tmdb",
    }


def test_first_import_shell_renders_for_admin(client: TestClient) -> None:
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
    assert "Download sample CSV" in page.text
    assert "XLSX imports read the first worksheet." in page.text


def test_onboarding_import_shell_uses_first_movie_copy(client: TestClient) -> None:
    page = client.get("/ui/onboarding/import")

    assert page.status_code == 200
    assert "<h1>Add your first movies</h1>" in page.text


def test_first_import_sample_csv_downloads_for_admin(client: TestClient) -> None:
    response = client.get("/ui/first-import/sample.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="vault966-first-import-sample.csv"'
    )
    assert "Title,Time,Director,Year" in response.text


def test_first_import_reviewer_cannot_open_wizard(
    client: TestClient,
    login_profile,
) -> None:
    login_profile(2)

    page = client.get("/ui/first-import", follow_redirects=False)

    assert page.status_code == 403


def test_first_import_upload_requires_same_origin(
    client: TestClient,
    login_profile,
) -> None:
    login_profile(1)
    content = _csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1")

    missing_origin = client.post(
        "/ui/first-import/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        follow_redirects=False,
    )
    cross_origin = client.post(
        "/ui/first-import/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        headers={"Origin": "http://evil.test"},
        follow_redirects=False,
    )

    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403


def test_first_import_upload_stages_source_snapshot_preview(
    client: TestClient,
    db_session,
) -> None:
    before = db_session.query(Movie).count()
    response = client.post(
        "/ui/first-import/upload",
        files={
            "source_file": (
                "source.csv",
                _csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/first-import/")
    snapshot_id = int(response.headers["location"].split("/")[-2])
    snapshot = db_session.get(SourceSnapshot, snapshot_id)
    assert snapshot.status == "draft"
    assert snapshot.row_count == 1
    assert snapshot.rows[0].normalized_title == "arrival"
    assert snapshot.rows[0].runtime == 116
    assert snapshot.rows[0].year == 2016
    assert db_session.query(Movie).count() == before


def test_first_import_upload_missing_columns_returns_recovery_copy(client: TestClient) -> None:
    response = client.post(
        "/ui/first-import/upload",
        files={"source_file": ("source.csv", b"Name,Watched\nArrival,yes\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/first-import?error=missing_columns"
    page = client.get(response.headers["location"])
    assert "start from the sample CSV" in page.text


def test_first_import_upload_redirect_uses_fixed_error_code_for_source_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/ui/first-import/upload",
        files={
            "source_file": (
                "source.csv",
                _csv("Arrival,not-a-runtime,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/first-import?error=invalid_runtime"
    assert "not-a-runtime" not in response.headers["location"]
    page = client.get(response.headers["location"])
    assert "Use minutes, H:MM, or H:MM:SS." in page.text


def test_first_import_auto_creates_high_confidence_tmdb_match(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate()],
    )

    result = source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    assert result.created_count == 1
    movie = db_session.query(Movie).filter(Movie.title == "Arrival").one()
    assert movie.tmdb_id == 329865
    assert movie.imdb_id == "tt2543164"
    assert movie.poster_url
    assert {genre.name for genre in movie.genres} == {"Science Fiction", "Drama"}
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .one()
    )
    assert match.match_type == "auto_create"
    assert match.movie_id == movie.id
    providers = {
        record.provider
        for record in db_session.query(MovieIngestProvenance)
        .filter(MovieIngestProvenance.movie_id == movie.id)
        .all()
    }
    assert {"collection_source", "tmdb", "omdb"} <= providers


def test_new_additions_csv_exports_only_high_confidence_auto_created_rows(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv(
            "Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1",
            "Solaris,2:46:00,Andrei Tarkovsky,1972,Sci-Fi,PG,09/26/72,1",
            "Unknown Title,1:30:00,Unknown,2020,Drama,PG,01/01/20,0",
        ),
        profile_id=1,
    )

    def candidates(title: str, year: int | None, limit: int = 3) -> list[dict]:
        if title == "Arrival":
            return [_candidate()]
        if title == "Solaris":
            return [
                _candidate(
                    title="Solaris",
                    year=1972,
                    runtime=166,
                    tmdb_id=593,
                    imdb_id="tt0069293",
                    confidence=0.82,
                )
            ]
        return []

    monkeypatch.setattr(source_sync, "lookup_movie_candidates", candidates)
    source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    response = client.get(f"/ui/source-sync/{snapshot.id}/new-additions.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="vault966-source-{snapshot.id}-new-additions.csv"'
    )
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["source_snapshot_id"] == str(snapshot.id)
    assert rows[0]["vault_id"]
    assert rows[0]["match_confidence"] == "0.99"
    assert rows[0]["title"] == "Arrival"
    assert rows[0]["year"] == "2016"
    assert rows[0]["runtime"] == "116"
    assert rows[0]["director"] == "Denis Villeneuve"
    assert rows[0]["hd"] == "HD"
    assert rows[0]["status"] == "high_confidence_added"


def test_new_additions_csv_neutralizes_formula_leading_source_fields(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("=Formula Title,1:56:00,+Director,2016,-Genre,@Rating,=ReleaseDate,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate(title=title, year=year or 2016, confidence=0.99)],
    )
    source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    response = client.get(f"/ui/source-sync/{snapshot.id}/new-additions.csv")

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["title"] == "'=Formula Title"
    assert rows[0]["director"] == "'+Director"
    assert rows[0]["genre"] == "'-Genre"
    assert rows[0]["content_rating"] == "'@Rating"
    assert rows[0]["release_date"] == "'=ReleaseDate"


def test_spreadsheet_formula_neutralizer_escapes_all_dangerous_prefixes() -> None:
    assert _neutralize_spreadsheet_formula("=SUM(1,1)") == "'=SUM(1,1)"
    assert _neutralize_spreadsheet_formula("+SUM(1,1)") == "'+SUM(1,1)"
    assert _neutralize_spreadsheet_formula("-SUM(1,1)") == "'-SUM(1,1)"
    assert _neutralize_spreadsheet_formula("@SUM(1,1)") == "'@SUM(1,1)"
    assert _neutralize_spreadsheet_formula("\tSUM(1,1)") == "'\tSUM(1,1)"
    assert _neutralize_spreadsheet_formula("\rSUM(1,1)") == "'\rSUM(1,1)"
    assert _neutralize_spreadsheet_formula("Arrival") == "Arrival"
    assert _neutralize_spreadsheet_formula(2016) == 2016


def test_vault_health_links_new_additions_export_when_high_confidence_rows_exist(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate()],
    )
    source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    page = client.get("/ui/movies/health")

    assert page.status_code == 200
    assert "Download new additions CSV" in page.text
    assert f'href="/ui/source-sync/{snapshot.id}/new-additions.csv"' in page.text


def test_first_import_rejects_low_confidence_from_auto_create(
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate(confidence=0.82)],
    )

    result = source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    assert result.created_count == 0
    assert result.review_count == 1
    assert db_session.query(Movie).filter(Movie.title == "Arrival").count() == 0


def test_first_import_rejects_duplicate_external_id_from_auto_create(
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate(tmdb_id=78, imdb_id="tt0083658")],
    )

    result = source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    assert result.created_count == 0
    assert result.duplicate_conflict_count == 1
    assert db_session.query(Movie).filter(Movie.title == "Arrival").count() == 0


def test_first_import_auto_create_activates_snapshot_and_routes_remaining_rows(
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv(
            "Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1",
            "Solaris,2:46:00,Andrei Tarkovsky,1972,Sci-Fi,PG,09/26/72,1",
            "Unknown Title,1:30:00,Unknown,2020,Drama,PG,01/01/20,0",
            "Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,R,06/25/82,1",
        ),
        profile_id=1,
    )

    def candidates(title: str, year: int | None, limit: int = 3) -> list[dict]:
        if title == "Arrival":
            return [_candidate()]
        if title == "Solaris":
            return [
                _candidate(
                    title="Solaris",
                    year=1972,
                    runtime=166,
                    tmdb_id=593,
                    imdb_id="tt0069293",
                    confidence=0.82,
                )
            ]
        return []

    monkeypatch.setattr(source_sync, "lookup_movie_candidates", candidates)

    result = source_sync.apply_first_import_auto_create(
        db_session,
        snapshot_id=snapshot.id,
        profile_id=1,
    )

    db_session.refresh(snapshot)
    report = source_sync.first_import_report(db_session, snapshot_id=snapshot.id)
    groups = source_sync.partition_source_review_queue(
        source_sync.get_source_review_queue(db_session, snapshot=snapshot)
    )

    assert snapshot.status == "active"
    assert result.created_count == 1
    assert report.created_count == 1
    assert report.review_count == 1
    assert report.duplicate_conflict_count == 1
    assert report.source_only_count == 1
    assert report.remaining_count == 3
    assert len(groups["ambiguous"]) == 1
    assert len(groups["duplicates"]) == 1
    assert len(groups["new"]) == 1


def test_first_import_auto_create_redirects_to_report(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )
    monkeypatch.setattr(
        source_sync,
        "lookup_movie_candidates",
        lambda title, year, limit=3: [_candidate()],
    )

    response = client.post(
        f"/ui/first-import/{snapshot.id}/auto-create",
        follow_redirects=False,
    )
    report = client.get(f"/ui/first-import/{snapshot.id}/report")

    assert response.status_code == 303
    assert response.headers["location"] == f"/ui/first-import/{snapshot.id}/report"
    assert report.status_code == 200
    assert "<h1>First import report</h1>" in report.text
    assert "1 high-confidence movies created" in report.text
    assert "Download new additions CSV" in report.text
    assert f'href="/ui/source-sync/{snapshot.id}/new-additions.csv"' in report.text


def test_first_import_auto_create_redirect_uses_fixed_error_code(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
        profile_id=1,
    )

    def fail_auto_create(*args, **kwargs):
        raise source_sync.SourceSyncError("Invalid year '<script>remote</script>'")

    monkeypatch.setattr(first_import_ui, "apply_first_import_auto_create", fail_auto_create)

    response = client.post(
        f"/ui/first-import/{snapshot.id}/auto-create",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/first-import?error=invalid_year"
    assert "script" not in response.headers["location"]
    page = client.get(response.headers["location"])
    assert "Use a four-digit release year." in page.text


def test_first_import_preview_shows_projected_outcome_counts(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    snapshot = source_sync.create_draft_snapshot(
        db_session,
        filename="source.csv",
        content=_csv(
            "Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1",
            "Solaris,2:46:00,Andrei Tarkovsky,1972,Sci-Fi,PG,09/26/72,1",
            "Unknown Title,1:30:00,Unknown,2020,Drama,PG,01/01/20,0",
        ),
        profile_id=1,
    )

    def candidates(title: str, year: int | None, limit: int = 3) -> list[dict]:
        if title == "Arrival":
            return [_candidate()]
        if title == "Solaris":
            return [_candidate(title="Solaris", year=1972, tmdb_id=593, confidence=0.82)]
        return []

    monkeypatch.setattr(source_sync, "lookup_movie_candidates", candidates)

    page = client.get(f"/ui/first-import/{snapshot.id}/preview")

    assert page.status_code == 200
    assert "Projected import outcome counts" in page.text
    assert "Safe create" in page.text
    assert "Needs review" in page.text
    assert "Manual create" in page.text
