from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import event

from api.config import settings
from api.deps.auth import require_same_origin
from api.models.movie import Movie
from api.models.person import RoleType
from api.models.source_sync import (
    OwnedMovieCopy,
    SourceFieldDecision,
    SourceReconciliationMatch,
    SourceSnapshot,
)
from api.services import source_sync
from api.services.source_sync import (
    SourceSyncError,
    build_research_links,
    clean_research_title,
    get_source_review_queue,
    parse_directors,
)


def _csv(*rows: str) -> bytes:
    header = "Title,Time,Director,Year,Genre,Content Rating,Release Date,HD"
    return ("\n".join((header, *rows)) + "\n").encode()


def _xlsx(rows: list[list[str]]) -> bytes:
    def column_name(index: int) -> str:
        name = ""
        index += 1
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(ord("A") + remainder) + name
        return name

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            reference = f"{column_name(column_index)}{row_index}"
            cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Movies" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def _xlsx_archive(
    sheet_xml: str,
    *,
    shared_strings_xml: str | None = None,
    compression: int = zipfile.ZIP_STORED,
    extra_members: int = 0,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "</Types>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Movies" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        if shared_strings_xml is not None:
            archive.writestr("xl/sharedStrings.xml", shared_strings_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        for index in range(extra_members):
            archive.writestr(f"xl/extra/{index}.xml", "<extra/>")
    return buffer.getvalue()


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


def test_parse_directors_accepts_comma_and_ampersand_separators() -> None:
    assert parse_directors("Kelly Asbury, Andrew Adamson & Conrad Vernon") == (
        "Kelly Asbury",
        "Andrew Adamson",
        "Conrad Vernon",
    )


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


def test_source_sync_status_and_history_live_on_collection_health(client: TestClient) -> None:
    _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1"),
    )

    source_sync = client.get("/ui/source-sync", follow_redirects=False)
    health = client.get("/ui/movies/health")

    assert source_sync.status_code == 302
    assert source_sync.headers["location"] == ("/ui/movies/health#source-synchronization")
    assert "Latest confirmed source" in health.text
    assert "Need attention" in health.text
    assert "Add one movie" in health.text
    assert "Full source refresh" in health.text
    assert "Upload collection file" in health.text
    assert "Match breakdown" in health.text
    assert "Audit trail" in health.text
    assert "Auto-matched" in health.text
    assert "Manually matched" in health.text
    assert '<details class="page-shell source-health" id="source-synchronization">' in health.text
    assert (
        '<details class="page-shell source-health" id="source-synchronization" open>'
        not in health.text
    )


def test_source_upload_errors_return_to_collection_health(client: TestClient) -> None:
    response = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("bad.csv", b"Title,Year\nMovie,2020\n", "text/csv")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/ui/movies/health?error=")
    assert response.headers["location"].endswith("#source-synchronization")


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


def test_source_sync_accepts_common_case_insensitive_headers(
    client: TestClient,
    db_session,
) -> None:
    content = (
        "movie title,runtime min,directors,release year,rating,quality\n"
        "Blade Runner,117,Ridley Scott,1982,PG,HD\n"
    ).encode()

    snapshot_id = _upload_and_confirm(client, content)

    row = db_session.get(SourceSnapshot, snapshot_id).rows[0]
    assert row.title == "Blade Runner"
    assert row.runtime == 117
    assert row.director == "Ridley Scott"
    assert row.year == 1982
    assert row.content_rating == "PG"
    assert row.hd is True


def test_source_sync_accepts_xlsx_upload(client: TestClient, db_session) -> None:
    content = _xlsx(
        [
            ["Movie Title", "Runtime", "Director(s)", "Release Year", "Genres", "Rated"],
            ["Arrival", "1h 56m", "Denis Villeneuve", "2016.0", "Sci-Fi", "PG-13"],
        ]
    )

    upload = client.post(
        "/ui/source-sync/upload",
        files={
            "source_file": (
                "source.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        follow_redirects=False,
    )

    assert upload.status_code == 303
    snapshot_id = int(upload.headers["location"].split("/")[-2])
    row = db_session.get(SourceSnapshot, snapshot_id).rows[0]
    assert row.title == "Arrival"
    assert row.runtime == 116
    assert row.director == "Denis Villeneuve"
    assert row.year == 2016
    assert row.genre == "Sci-Fi"
    assert row.content_rating == "PG-13"


def test_source_sync_rejects_xlsx_expansion_before_xml_parse(monkeypatch) -> None:
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{' ' * 1024}</sheetData>"
        "</worksheet>"
    )
    content = _xlsx_archive(sheet_xml)
    monkeypatch.setattr(source_sync, "MAX_XLSX_UNCOMPRESSED_BYTES", 128)

    def fail_fromstring(_content):
        raise AssertionError("XML should not be materialized for oversized XLSX archives")

    monkeypatch.setattr(source_sync.ElementTree, "fromstring", fail_fromstring)

    with pytest.raises(SourceSyncError, match="expands beyond"):
        source_sync.parse_source_xlsx(content)


def test_source_sync_rejects_xlsx_member_count_before_xml_parse(monkeypatch) -> None:
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData/>"
        "</worksheet>"
    )
    content = _xlsx_archive(sheet_xml, extra_members=3)
    monkeypatch.setattr(source_sync, "MAX_XLSX_MEMBERS", 4)

    def fail_fromstring(_content):
        raise AssertionError("XML should not be materialized for too many XLSX parts")

    monkeypatch.setattr(source_sync.ElementTree, "fromstring", fail_fromstring)

    with pytest.raises(SourceSyncError, match="too many parts"):
        source_sync.parse_source_xlsx(content)


def test_source_sync_rejects_high_compression_xlsx_before_xml_parse(monkeypatch) -> None:
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{'A' * 2048}</sheetData>"
        "</worksheet>"
    )
    content = _xlsx_archive(sheet_xml, compression=zipfile.ZIP_DEFLATED)
    monkeypatch.setattr(source_sync, "MAX_XLSX_COMPRESSION_RATIO", 2)

    def fail_fromstring(_content):
        raise AssertionError("XML should not be materialized for high-compression XLSX")

    monkeypatch.setattr(source_sync.ElementTree, "fromstring", fail_fromstring)

    with pytest.raises(SourceSyncError, match="compression ratio"):
        source_sync.parse_source_xlsx(content)


def test_source_sync_rejects_xlsx_shared_string_count(monkeypatch) -> None:
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData>'
        "</worksheet>"
    )
    shared_strings_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>Title</t></si><si><t>Time</t></si>"
        "</sst>"
    )
    monkeypatch.setattr(source_sync, "MAX_XLSX_SHARED_STRINGS", 1)

    with pytest.raises(SourceSyncError, match="too many shared strings"):
        source_sync.parse_source_xlsx(
            _xlsx_archive(sheet_xml, shared_strings_xml=shared_strings_xml)
        )


def test_source_sync_rejects_xlsx_row_and_cell_caps(monkeypatch) -> None:
    row_xml = '<row r="1"><c r="A1" t="inlineStr"><is><t>Title</t></is></c></row>'
    two_rows = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{row_xml}{row_xml}</sheetData>"
        "</worksheet>"
    )
    monkeypatch.setattr(source_sync, "MAX_XLSX_ROWS", 1)
    with pytest.raises(SourceSyncError, match="more than 5000 rows"):
        source_sync.parse_source_xlsx(_xlsx_archive(two_rows))

    three_cells = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Title</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Time</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Director</t></is></c>'
        "</row></sheetData></worksheet>"
    )
    monkeypatch.setattr(source_sync, "MAX_XLSX_ROWS", source_sync.MAX_SOURCE_ROWS + 25)
    monkeypatch.setattr(source_sync, "MAX_XLSX_CELLS", 2)
    with pytest.raises(SourceSyncError, match="too many cells"):
        source_sync.parse_source_xlsx(_xlsx_archive(three_cells))


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


def test_source_sync_mutations_require_same_origin(client: TestClient, login_profile) -> None:
    login_profile(1)
    content = _csv("Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1")

    missing_origin = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        follow_redirects=False,
    )
    cross_origin = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        headers={"Origin": "http://evil.test"},
        follow_redirects=False,
    )
    allowed_upload = client.post(
        "/ui/source-sync/upload",
        files={"source_file": ("source.csv", content, "text/csv")},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )

    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403
    assert allowed_upload.status_code == 303

    snapshot_id = int(allowed_upload.headers["location"].split("/")[-2])
    missing_confirm_origin = client.post(
        f"/ui/source-sync/{snapshot_id}/confirm",
        follow_redirects=False,
    )
    cross_confirm_origin = client.post(
        f"/ui/source-sync/{snapshot_id}/confirm",
        headers={"Origin": "http://evil.test"},
        follow_redirects=False,
    )
    allowed_confirm = client.post(
        f"/ui/source-sync/{snapshot_id}/confirm",
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )

    assert missing_confirm_origin.status_code == 403
    assert cross_confirm_origin.status_code == 403
    assert allowed_confirm.status_code == 303


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


def test_review_queue_can_select_and_navigate_source_rows(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,,1983,Sci-Fi,PG,6/25/82,1",
            "The Matrix,2:16:00,,2000,Action,R,3/31/99,1",
        ),
    )
    matches = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .order_by(SourceReconciliationMatch.id)
        .all()
    )

    response = client.get(f"/ui/movies/health?view=differences&row={matches[1].source_row_id}")

    assert response.status_code == 200
    assert "2 of 2 in Differences" in response.text
    assert "The Matrix" in response.text
    assert f"row={matches[0].source_row_id}" in response.text


def test_source_review_queue_batches_field_decision_queries(client: TestClient, db_session) -> None:
    _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,,1983,Sci-Fi,PG,6/25/82,1",
            "The Matrix,2:16:00,,2000,Action,R,3/31/99,1",
        ),
    )
    decision_queries = 0

    def count_decision_queries(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        nonlocal decision_queries
        if (
            statement.lstrip().lower().startswith("select")
            and "source_field_decisions" in statement.lower()
        ):
            decision_queries += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_decision_queries)
    try:
        queue = get_source_review_queue(db_session)
    finally:
        event.remove(engine, "before_cursor_execute", count_decision_queries)

    assert len(queue) == 2
    assert decision_queries == 1


def test_ambiguous_row_can_create_new_vault_entry(client: TestClient, db_session) -> None:
    for index, movie in enumerate(db_session.query(Movie).order_by(Movie.id), start=1):
        movie.vault_id = f"V{index:04d}"
    db_session.commit()
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

    response = client.post(
        f"/ui/movies/health/review/source-row/{match.source_row_id}/create?view=ambiguous",
        follow_redirects=False,
    )

    assert response.status_code == 303
    created = db_session.query(Movie).filter(Movie.title == "Blade Runner").all()
    assert len(created) == 2
    assert created[-1].vault_id == "V0034"


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
        f"/ui/movies/health/review/source-row/{match.source_row_id}/field/year/use_source",
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
    client.post(
        f"/ui/movies/health/review/source-row/{match.source_row_id}/field/year/needs_research"
    )
    client.post(f"/ui/movies/health/review/source-row/{match.source_row_id}/field/year/keep_vault")

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
    assert decisions[0].resolved_at is not None
    assert decisions[1].resolved_at is not None


def test_bulk_accept_uses_source_for_all_matched_differences(
    client: TestClient, db_session
) -> None:
    for index, movie in enumerate(db_session.query(Movie).order_by(Movie.id), start=1):
        movie.vault_id = f"V{index:04d}"
    db_session.commit()
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,Ridley Scott,1983,Sci-Fi,PG,6/25/82,1",
            "The Matrix,2:16:00,Lana Wachowski & Lilly Wachowski,2000,Action,R,3/31/99,1",
            "Unknown Match,3:00:00,Someone Else,2024,Drama,PG,1/1/24,1",
        ),
    )
    blade_match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id, title="Blade Runner")
        .one()
    )
    client.post(
        f"/ui/movies/health/review/source-row/{blade_match.source_row_id}/field/year/needs_research"
    )

    response = client.post(
        "/ui/movies/health/review/source-accept-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert (
        "Applied%204%20source%20values%20across%202%20Vault%20entries"
        in response.headers["location"]
    )
    db_session.expire_all()
    blade = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()
    matrix = db_session.query(Movie).filter(Movie.title == "The Matrix").one()
    assert blade.year == 1983
    assert matrix.year == 2000
    assert blade.vault_id == "V0001"
    assert matrix.vault_id == "V0002"
    decisions = (
        db_session.query(SourceFieldDecision)
        .filter(SourceFieldDecision.decision == "use_source")
        .all()
    )
    assert {decision.field_name for decision in decisions} == {"year", "director"}
    review = client.get("/ui/movies/health?view=differences")
    assert "Differences queue is clear" in review.text
    assert "Ambiguous" in review.text


def test_bulk_accept_skips_conflicting_rows_for_the_same_movie_field(
    client: TestClient, db_session
) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,Ridley Scott,1983,Sci-Fi,PG,6/25/82,1",
            "Blade Runner,1:57:00,Ridley Scott,1982,Sci-Fi,PG,6/25/82,1",
        ),
    )

    response = client.post(
        "/ui/movies/health/review/source-accept-all",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "Applied%201%20source%20values" in response.headers["location"]
    assert "Left%201%20conflicting%20source%20value%20in%20review" in response.headers["location"]
    db_session.expire_all()
    assert db_session.get(Movie, 1).year == 1982
    decisions = (
        db_session.query(SourceFieldDecision)
        .filter(SourceFieldDecision.decision == "use_source")
        .all()
    )
    assert {decision.field_name for decision in decisions} == {"director"}
    assert (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .count()
        == 2
    )
    review = client.get("/ui/movies/health?view=differences")
    assert "Accept all source values" not in review.text


def test_review_page_always_shows_direct_and_search_links(client: TestClient, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.vault_id = "V0001"
    db_session.commit()
    _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,,1983,Sci-Fi,PG,6/25/82,1"),
    )

    response = client.get("/ui/movies/health?view=differences")

    assert response.status_code == 200
    assert '<details class="research-links">' in response.text
    assert '<details class="research-links" open>' not in response.text
    assert "External sources" in response.text
    assert "Open current TMDB" in response.text
    assert "https://www.themoviedb.org/movie/78" in response.text
    assert "Open current IMDb" in response.text
    assert "https://www.imdb.com/title/tt0083658/" in response.text
    assert "Search TMDB" in response.text
    assert "Search IMDb" in response.text
    assert 'rel="noopener noreferrer"' in response.text


def test_research_links_clean_editions_and_reject_invalid_direct_ids() -> None:
    movie = Movie(
        title="The Boss",
        year=2016,
        imdb_id="javascript:bad",
        tmdb_id=0,
    )

    links = build_research_links(
        source_title="The Boss (Unrated)",
        source_year=2016,
        source_director=None,
        movie=movie,
    )

    assert clean_research_title("The Boss (Unrated)") == "The Boss"
    assert (
        clean_research_title("American Gangster (Unrated Extended Edition)") == "American Gangster"
    )
    assert links.current == ()
    assert links.search_title == "The Boss"
    assert "The+Boss+2016" in links.searches[0].url


def test_defer_movie_moves_all_conflicts_and_shows_next(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv(
            "Blade Runner,1:57:00,Someone Else,1983,Sci-Fi,PG,6/25/82,1",
            "The Matrix,2:16:00,Someone Else,2000,Action,R,3/31/99,1",
        ),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .order_by(SourceReconciliationMatch.id)
        .first()
    )

    response = client.post(
        f"/ui/movies/health/review/source-row/{match.source_row_id}/defer?view=differences",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "view=differences" in response.headers["location"]
    research = client.get("/ui/movies/health?view=research")
    differences = client.get("/ui/movies/health?view=differences")
    assert "Blade Runner" in research.text
    assert "Needs research" in research.text
    assert "The Matrix" in differences.text
    assert "Blade Runner" not in differences.text
    decisions = (
        db_session.query(SourceFieldDecision)
        .filter(SourceFieldDecision.source_row_id == match.source_row_id)
        .all()
    )
    assert {decision.field_name for decision in decisions} == {
        "year",
        "director",
    }


def test_latest_source_decision_can_be_undone(client: TestClient, db_session) -> None:
    snapshot_id = _upload_and_confirm(
        client,
        _csv("Blade Runner,1:57:00,,1983,Sci-Fi,PG,6/25/82,1"),
    )
    match = (
        db_session.query(SourceReconciliationMatch)
        .join(SourceReconciliationMatch.source_row)
        .filter_by(snapshot_id=snapshot_id)
        .one()
    )
    decision = client.post(
        f"/ui/movies/health/review/source-row/{match.source_row_id}/field/year/use_source",
        follow_redirects=False,
    )
    query = parse_qs(urlparse(decision.headers["location"]).query)
    decision_id = int(query["undo_decision"][0])
    db_session.expire_all()
    assert db_session.get(Movie, 1).year == 1983

    undo = client.post(
        f"/ui/movies/health/review/source-decision/{decision_id}/undo?view=differences",
        follow_redirects=False,
    )

    assert undo.status_code == 303
    db_session.expire_all()
    assert db_session.get(Movie, 1).year == 1982
    assert db_session.get(SourceFieldDecision, decision_id).undone_at is not None


def test_review_routes_require_profile_auth_when_enabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)

    response = client.get("/ui/movies/health", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_same_origin_guard_rejects_cross_origin(monkeypatch) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    base_scope = {
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "server": ("vault.local", 443),
        "path": "/ui/movies/health/review/source-row/1/field/year/keep_vault",
        "query_string": b"",
        "headers": [(b"host", b"vault.local")],
    }
    with pytest.raises(HTTPException) as exc_info:
        require_same_origin(Request(base_scope))
    assert exc_info.value.status_code == 403

    allowed_scope = {
        **base_scope,
        "headers": [
            (b"host", b"vault.local"),
            (b"origin", b"https://vault.local"),
        ],
    }
    require_same_origin(Request(allowed_scope))


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
        f"/ui/movies/health/review/source-row/{match.source_row_id}/field/director/use_source",
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
        f"/ui/movies/health/review/source-row/{match.source_row_id}/create",
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
        f"/ui/movies/health/review/source-row/{matches[1].source_row_id}/dismiss-duplicate",
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
