from __future__ import annotations

from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.person import RoleType
from api.models.source_sync import (
    OwnedMovieCopy,
    SourceFieldDecision,
    SourceReconciliationMatch,
    SourceSnapshot,
)


def _csv(*rows: str) -> bytes:
    header = "Title,Time,Director,Year,Genre,Content Rating,Release Date,HD"
    return ("\n".join((header, *rows)) + "\n").encode()


def _upload_and_confirm(client: TestClient, content: bytes) -> int:
    upload = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert upload.status_code == 303
    snapshot_id = int(upload.headers["location"].split("/")[-2])
    confirm = client.post(
        f"/ui/source-sync/{snapshot_id}/confirm",
        follow_redirects=False,
    )
    assert confirm.status_code == 303
    return snapshot_id


def test_source_sync_upload_preview_and_confirm(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1",
            "Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1",
        ),
    )

    snapshot = db_session.get(SourceSnapshot, snapshot_id)
    assert snapshot.status == "active"
    assert snapshot.row_count == 2
    matches = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .all()
    )
    assert {match.match_type for match in matches} == {"exact", "source_only"}


def test_source_sync_accepts_minute_second_runtime(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Short Film,14:35.583,Example Director,2020,Drama,NR,1/1/20,1"),
    )
    snapshot = db_session.get(SourceSnapshot, snapshot_id)
    assert snapshot.rows[0].runtime == 15


def test_source_sync_accepts_reordered_columns(client: TestClient, db_session) -> None:
    content = (
        "HD,Year,Director,Title,Time\n" "1,1982,Ridley Scott,Blade Runner,1:57:00\n"
    ).encode()
    snapshot_id = _upload_and_confirm(client, content)
    snapshot = db_session.get(SourceSnapshot, snapshot_id)
    assert snapshot.rows[0].title == "Blade Runner"
    assert snapshot.rows[0].hd is True


def test_source_sync_rejects_malformed_and_repeated_files(client: TestClient) -> None:
    malformed = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("bad.csv", b"Title,Year\nBlade Runner,1982\n", "text/csv")},
        follow_redirects=False,
    )
    assert malformed.status_code == 303
    assert "error=" in malformed.headers["location"]

    content = _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1")
    first = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert first.status_code == 303
    repeated = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        follow_redirects=False,
    )
    assert repeated.status_code == 303
    assert "already%20uploaded" in repeated.headers["location"]


def test_source_sync_rejects_overlong_identity_fields(client: TestClient) -> None:
    response = client.post(
        "/ui/source-sync/upload",
        files={
            "source_file": (
                "source.csv",
                _csv(f"{'A' * 301},1:30:00,Director,2020,Drama,PG,1/1/20,1"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "exceeds%20300%20characters" in response.headers["location"]


def test_unsupported_title_match_remains_ambiguous(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,3:00:00,Someone Else,1983,Sci-Fi,PG,6/25/82,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )
    assert match.match_type == "ambiguous"
    assert match.movie_id is None


def test_field_decision_updates_only_selected_field_and_preserves_vault_id(
    client: TestClient, db_session
) -> None:
    movie = db_session.get(Movie, 1)
    movie.vault_id = "V0001"
    db_session.commit()
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1983,Sci-Fi,PG,6/25/82,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )

    response = client.post(
        f"/ui/review/source-row/{match.source_row_id}/field/year/use_source",
        follow_redirects=False,
    )

    assert response.status_code == 303
    db_session.expire_all()
    movie = db_session.get(Movie, 1)
    assert movie.year == 1983
    assert movie.runtime == 117
    assert movie.vault_id == "V0001"
    decision = db_session.query(SourceFieldDecision).one()
    assert decision.previous_value == "1982"
    assert decision.selected_value == "1983"
    assert decision.decision == "use_source"


def test_field_decisions_preserve_full_history(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1983,Sci-Fi,PG,6/25/82,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )
    client.post(f"/ui/review/source-row/{match.source_row_id}/field/year/needs_research")
    client.post(f"/ui/review/source-row/{match.source_row_id}/field/year/keep_vault")

    decisions = (
        db_session.query(SourceFieldDecision)
        .filter(SourceFieldDecision.source_row_id == match.source_row_id)
        .order_by(SourceFieldDecision.id)
        .all()
    )
    assert [decision.decision for decision in decisions] == [
        "needs_research",
        "keep_vault",
    ]
    assert decisions[0].resolved_at is None
    assert decisions[1].resolved_at is not None


def test_director_decision_updates_roles(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )

    response = client.post(
        f"/ui/review/source-row/{match.source_row_id}/field/director/use_source",
        follow_redirects=False,
    )

    assert response.status_code == 303
    db_session.expire_all()
    movie = db_session.get(Movie, 1)
    directors = {role.person.name for role in movie.roles if role.role_type == RoleType.DIRECTOR}
    assert directors == {"Ridley Scott"}


def test_hd_is_stored_on_owned_copy(client: TestClient, db_session) -> None:
    _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1"),
    )

    copy = db_session.query(OwnedMovieCopy).one()
    assert copy.movie_id == 1
    assert copy.hd is True
    assert not hasattr(db_session.get(Movie, 1), "hd")


def test_source_only_row_can_create_next_vault_entry(client: TestClient, db_session) -> None:
    for index, movie in enumerate(db_session.query(Movie).order_by(Movie.id), start=1):
        movie.vault_id = f"V{index:04d}"
    db_session.commit()
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Arrival,1:56:00,Denis Villeneuve,2016,Sci-Fi,PG-13,11/11/16,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )

    response = client.post(
        f"/ui/review/source-row/{match.source_row_id}/create",
        follow_redirects=False,
    )

    assert response.status_code == 303
    created = db_session.query(Movie).filter(Movie.title == "Arrival").one()
    assert created.vault_id == "V0034"
    assert created.year == 2016
    assert any(role.role_type == RoleType.DIRECTOR for role in created.roles)


def test_duplicate_rows_require_disposition(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1",
            "Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1",
        ),
    )
    matches = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .order_by(SourceReconciliationMatch.id)
        .all()
    )
    assert [match.match_type for match in matches] == ["exact", "duplicate"]

    response = client.post(
        f"/ui/review/source-row/{matches[1].source_row_id}/dismiss-duplicate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.expire_all()
    assert db_session.get(SourceReconciliationMatch, matches[1].id).match_type == (
        "duplicate_ignored"
    )


def test_missing_source_rows_do_not_change_vault(client: TestClient, db_session) -> None:
    before = db_session.query(Movie).count()
    _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1"),
    )
    db_session.expire_all()
    assert db_session.query(Movie).count() == before
    assert db_session.get(Movie, 2).title == "The Matrix"


def test_new_snapshot_supersedes_previous_baseline(client: TestClient, db_session) -> None:
    first_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1"),
    )
    second_id = _upload_and_confirm(
        client,
        _csv("The Matrix,2:16:00,Lana Wachowski,1999,Action,R,3/31/99,1"),
    )
    db_session.expire_all()
    assert db_session.get(SourceSnapshot, first_id).status == "superseded"
    assert db_session.get(SourceSnapshot, second_id).status == "active"
