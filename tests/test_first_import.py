from __future__ import annotations

from fastapi.testclient import TestClient

from api.models.movie import Movie, MovieIngestProvenance
from api.models.source_sync import SourceMovieRow, SourceReconciliationMatch, SourceSnapshot
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
    assert 'accept=".csv,text/csv"' in page.text


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
