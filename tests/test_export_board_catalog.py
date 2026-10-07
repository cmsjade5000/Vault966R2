from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.export_board_catalog import ExportError, build_catalog, export_catalog, main


def _movie_row(**overrides):
    row = {
        "id": 7,
        "vault_id": "v0007",
        "title": "Signal in the Dark",
        "year": 2024,
        "runtime": 101,
        "plot": "A careful astronomer follows a signal through a citywide blackout.",
        "imdb_rating": 8.1,
        "imdb_votes": 1200,
        "metascore": 76,
        "tomato_meter": 91,
        "tomato_audience": 88,
        "poster_url": "https://images.example.test/poster.jpg?token=secret",
        "backdrop_url": "http://images.example.test/backdrop.jpg",
        "where_to_watch": '["Blu-ray", "Kanopy", "Blu-ray"]',
        "keywords": '["signal", "night"]',
    }
    row.update(overrides)
    return row


def test_build_catalog_is_allowlisted_and_uses_stable_vault_keys():
    catalog, summary = build_catalog(
        [_movie_row()],
        genres={7: ["Science Fiction"]},
        moods={7: ["Mysterious"]},
        roles={
            7: [
                {"role_type": "ACTOR", "name": "Mara Vale", "billing_order": 1},
                {"role_type": "DIRECTOR", "name": "Ari North", "billing_order": None},
            ]
        },
        profile_id=3,
        preferences={7: {"liked": True, "watchlist": False}},
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    movie = catalog["movies"][0]
    assert movie["key"] == "V0007"
    assert movie["genres"] == ["Science Fiction"]
    assert movie["cast"] == ["Mara Vale"]
    assert movie["directors"] == ["Ari North"]
    assert movie["liked"] is True
    assert movie["watchlist"] is False
    assert movie["artwork"] == {"poster": "https://images.example.test/poster.jpg"}
    assert movie["where_to_watch"] == ["Blu-ray", "Kanopy"]
    assert movie["ratings"] == {
        "imdb": 8.1,
        "votes": 1200,
        "metascore": 76,
        "tomato": 91,
        "audience": 88,
    }
    serialized = json.dumps(catalog)
    assert '"id"' not in serialized
    assert "imdb_id" not in serialized
    assert "token" not in serialized
    assert summary["exported_records"] == 1


def test_missing_vault_id_fails_closed_without_deriving_internal_key():
    with pytest.raises(ExportError, match="lack a valid persisted Vault ID"):
        build_catalog([_movie_row(vault_id=None)])

    catalog, summary = build_catalog(
        [_movie_row(vault_id=None)],
        allow_missing_vault_id=True,
    )
    assert catalog["movies"] == []
    assert summary["skipped_missing_vault_id"] == 1


def _create_source_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE movies (
                id INTEGER PRIMARY KEY,
                vault_id TEXT,
                title TEXT,
                year INTEGER,
                runtime INTEGER,
                plot TEXT,
                imdb_rating REAL,
                imdb_votes INTEGER,
                metascore INTEGER,
                tomato_meter INTEGER,
                tomato_audience INTEGER,
                poster_url TEXT,
                backdrop_url TEXT,
                where_to_watch TEXT,
                keywords TEXT
            );
            CREATE TABLE genres (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE movie_genres (movie_id INTEGER, genre_id INTEGER);
            CREATE TABLE moods (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE movie_moods (movie_id INTEGER, mood_id INTEGER);
            CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                movie_id INTEGER,
                person_id INTEGER,
                role_type TEXT,
                billing_order INTEGER
            );
            CREATE TABLE movie_preferences (
                profile_id INTEGER,
                movie_id INTEGER,
                liked INTEGER,
                watchlist INTEGER
            );
            """
        )
        row = _movie_row()
        connection.execute(
            "INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            tuple(
                row[name]
                for name in (
                    "id",
                    "vault_id",
                    "title",
                    "year",
                    "runtime",
                    "plot",
                    "imdb_rating",
                    "imdb_votes",
                    "metascore",
                    "tomato_meter",
                    "tomato_audience",
                    "poster_url",
                    "backdrop_url",
                    "where_to_watch",
                    "keywords",
                )
            ),
        )
        connection.executemany("INSERT INTO genres VALUES (?, ?)", [(1, "Thriller")])
        connection.executemany("INSERT INTO movie_genres VALUES (?, ?)", [(7, 1)])
        connection.executemany("INSERT INTO moods VALUES (?, ?)", [(1, "Tense")])
        connection.executemany("INSERT INTO movie_moods VALUES (?, ?)", [(7, 1)])
        connection.executemany(
            "INSERT INTO people VALUES (?, ?)", [(1, "Mara Vale"), (2, "Ari North")]
        )
        connection.executemany(
            "INSERT INTO roles VALUES (?, ?, ?, ?, ?)",
            [(1, 7, 1, "ACTOR", 1), (2, 7, 2, "DIRECTOR", None)],
        )
        connection.executemany(
            "INSERT INTO movie_preferences VALUES (?, ?, ?, ?)",
            [(3, 7, 1, 0)],
        )
        connection.commit()


def test_export_catalog_reads_live_shape_without_mutation(tmp_path: Path):
    database = tmp_path / "vault.db"
    _create_source_database(database)
    before = database.read_bytes()

    catalog, summary = export_catalog(
        database,
        profile_id=3,
        generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )

    assert summary["source_records"] == 1
    assert catalog["movies"][0]["key"] == "V0007"
    assert catalog["movies"][0]["moods"] == ["Tense"]
    assert catalog["movies"][0]["cast"] == ["Mara Vale"]
    assert database.read_bytes() == before


def test_cli_dry_run_does_not_create_snapshot(tmp_path: Path, capsys):
    database = tmp_path / "vault.db"
    _create_source_database(database)
    output = tmp_path / "catalog.snapshot.json"

    assert main(["--database", str(database), "--output", str(output)]) == 0
    assert not output.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry-run"
    assert payload["exported_records"] == 1
