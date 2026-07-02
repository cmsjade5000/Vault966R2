import csv
import pathlib

from scripts.prepare_import_csv import Summary, clean_rows, load_rows


def test_load_rows_skips_leading_garbage_until_title_header(tmp_path: pathlib.Path):
    input_path = tmp_path / "dirty.csv"
    input_path.write_text(
        "exported from spreadsheet\n\nnotes,not,the,header\n Title , Year , imdb_id \nAlien (1979),1979,tt0078748\n",
        encoding="utf-8",
    )

    rows = load_rows(input_path)
    summary = Summary()
    cleaned = clean_rows(rows, summary)

    assert len(cleaned) == 1
    assert cleaned[0]["title"] == "Alien"
    assert cleaned[0]["year"] == 1979
    assert cleaned[0]["imdb_id"] == "tt0078748"
    assert summary.total_rows == 1
    assert summary.cleaned_titles == 1


def test_load_rows_keeps_existing_title_only_csv_behavior(tmp_path: pathlib.Path):
    input_path = tmp_path / "titles.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["title"])
        writer.writerow(["Solaris"])

    rows = load_rows(input_path)
    summary = Summary()
    cleaned = clean_rows(rows, summary)

    assert cleaned == [{"title": "Solaris", "year": ""}]
