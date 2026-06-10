import csv
import json
import pathlib

import pytest

from scripts.prepare_legacy_vault_csv import (
    LEGACY_COLUMNS,
    LegacyCsvError,
    normalize_legacy_row,
    prepare_legacy_vault_csv,
    read_legacy_csv,
    split_genres,
)


def _legacy_row(**overrides: str) -> dict[str, str]:
    row = {column: "" for column in LEGACY_COLUMNS}
    row.update(
        {
            "title": "Interstellar",
            "vault_id": "V966-002",
            "imdb_rating": "8.7",
            "rt_percent": "73.0",
            "director": "Christopher Nolan",
            "release_year": "2014.0",
            "genres": "Sci-Fi; Adventure",
            "runtime_min": "169",
            "verified_year": "2014",
            "top_billed_actor": "Matthew McConaughey",
            "top_3_actors": "Matthew McConaughey; Anne Hathaway; Jessica Chastain",
            "plot_summary": "Explorers travel through a wormhole.",
            "imdb_votes": "1,923,456",
            "imdb_id": "TT0816692",
            "tmdb_id": "157336.0",
        }
    )
    row.update(overrides)
    return row


def _write_legacy_csv(path: pathlib.Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEGACY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_split_genres_handles_all_legacy_delimiters_and_drops_nan():
    assert split_genres("Drama|Sci-Fi; nan, Comedy;drama") == [
        "Drama",
        "Sci-Fi",
        "Comedy",
    ]


def test_normalize_legacy_row_maps_fields_and_normalizes_numeric_values():
    staged = normalize_legacy_row(_legacy_row())

    assert staged["vault_id"] == "V966-002"
    assert staged["year"] == 2014
    assert staged["verified_year"] == 2014
    assert staged["runtime_min"] == 169
    assert staged["imdb_rating"] == 8.7
    assert staged["imdb_votes"] == 1923456
    assert staged["rt_score"] == 73
    assert staged["tmdb_id"] == 157336
    assert staged["imdb_id"] == "tt0816692"
    assert staged["genres"] == ["Science Fiction", "Adventure"]
    assert staged["plot"] == "Explorers travel through a wormhole."
    assert staged["director"] == "Christopher Nolan"
    assert staged["top_billed_actor"] == "Matthew McConaughey"
    assert staged["top_3_actors"].startswith("Matthew McConaughey")


def test_normalize_legacy_row_converts_nan_and_invalid_numbers_to_null():
    staged = normalize_legacy_row(
        _legacy_row(
            imdb_rating="nan",
            imdb_votes="unknown",
            runtime_min="90.5",
            genres="nan",
            director="NaN",
        )
    )

    assert staged["imdb_rating"] is None
    assert staged["imdb_votes"] is None
    assert staged["runtime_min"] is None
    assert staged["genres"] == []
    assert staged["director"] is None


def test_read_legacy_csv_rejects_non_exact_schema(tmp_path: pathlib.Path):
    input_path = tmp_path / "legacy.csv"
    input_path.write_text("title,vault_id\nAlien,V966-001\n", encoding="utf-8")

    with pytest.raises(LegacyCsvError, match="exact 21-column header"):
        read_legacy_csv(input_path)


def test_prepare_writes_staged_csv_and_machine_readable_review_report(
    tmp_path: pathlib.Path,
):
    input_path = tmp_path / "legacy.csv"
    output_path = tmp_path / "staged.csv"
    report_path = tmp_path / "review.json"
    rows = [
        _legacy_row(),
        _legacy_row(
            title="Interstellar Redux",
            vault_id="V966-003",
            imdb_id="tt0816692",
            tmdb_id="999",
        ),
        _legacy_row(
            title="Interstellar",
            vault_id="V966-004",
            release_year="2024",
            imdb_id="tt9999999",
            tmdb_id="157336",
        ),
    ]
    _write_legacy_csv(input_path, rows)
    original = input_path.read_bytes()

    report = prepare_legacy_vault_csv(input_path, output_path, report_path)

    assert input_path.read_bytes() == original
    with output_path.open(encoding="utf-8", newline="") as handle:
        staged_rows = list(csv.DictReader(handle))
    assert len(staged_rows) == 3
    assert json.loads(staged_rows[0]["genres"]) == ["Science Fiction", "Adventure"]
    assert staged_rows[0]["vault_id"] == "V966-002"
    assert staged_rows[0]["director"] == "Christopher Nolan"

    persisted_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted_report == report
    assert report["summary"]["requires_review"] is True
    assert report["summary"]["issue_counts"] == {
        "duplicate_imdb_id": 1,
        "duplicate_tmdb_id": 1,
        "title_year_conflict": 1,
        "verified_year_conflict": 1,
    }
    issue_types = {issue["type"] for issue in report["issues"]}
    assert issue_types == {
        "duplicate_imdb_id",
        "duplicate_tmdb_id",
        "title_year_conflict",
        "verified_year_conflict",
    }


def test_prepare_reports_invalid_numeric_values(tmp_path: pathlib.Path):
    input_path = tmp_path / "legacy.csv"
    output_path = tmp_path / "staged.csv"
    report_path = tmp_path / "review.json"
    _write_legacy_csv(input_path, [_legacy_row(runtime_min="feature length")])

    report = prepare_legacy_vault_csv(input_path, output_path, report_path)

    assert report["summary"]["issue_counts"] == {"invalid_numeric_value": 1}
    assert report["issues"][0] == {
        "type": "invalid_numeric_value",
        "row": 2,
        "field": "runtime_min",
        "value": "feature length",
    }


def test_prepare_reports_year_review_issues(tmp_path: pathlib.Path):
    input_path = tmp_path / "legacy.csv"
    output_path = tmp_path / "staged.csv"
    report_path = tmp_path / "review.json"
    _write_legacy_csv(
        input_path,
        [
            _legacy_row(
                title="Example (1999)",
                release_year="2000",
                verified_year="2001",
            ),
            _legacy_row(
                title="Unknown Year",
                release_year="",
                verified_year="",
                imdb_id="tt9999999",
                tmdb_id="999",
            ),
        ],
    )

    report = prepare_legacy_vault_csv(input_path, output_path, report_path)

    assert report["summary"]["issue_counts"] == {
        "missing_year": 1,
        "title_embedded_year_conflict": 1,
        "verified_year_conflict": 1,
    }


def test_prepare_rejects_reusing_input_as_output(tmp_path: pathlib.Path):
    input_path = tmp_path / "legacy.csv"
    _write_legacy_csv(input_path, [_legacy_row()])

    with pytest.raises(LegacyCsvError, match="paths must be different"):
        prepare_legacy_vault_csv(input_path, input_path, tmp_path / "review.json")
