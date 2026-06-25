from __future__ import annotations

import pathlib
from types import SimpleNamespace

from scripts import import_latest_enriched_csv


def _args(input_path: pathlib.Path, *, dry_run: bool) -> SimpleNamespace:
    return SimpleNamespace(
        input=str(input_path),
        dry_run=dry_run,
        no_network=False,
        allow_tmdb_only=False,
        encoding=None,
    )


def test_import_runs_poster_cache_after_success(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "enriched_movies.csv"
    input_path.write_text("title,year\nMovie,2026\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        import_latest_enriched_csv,
        "parse_args",
        lambda: _args(input_path, dry_run=False),
    )
    monkeypatch.setattr(
        import_latest_enriched_csv.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd),
    )

    assert import_latest_enriched_csv.main() == 0
    assert len(calls) == 2
    assert calls[0][1] == str(import_latest_enriched_csv.ETL_SCRIPT)
    assert calls[1][1] == str(import_latest_enriched_csv.POSTER_CACHE_SCRIPT)


def test_dry_run_does_not_cache_posters(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "enriched_movies.csv"
    input_path.write_text("title,year\nMovie,2026\n", encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        import_latest_enriched_csv,
        "parse_args",
        lambda: _args(input_path, dry_run=True),
    )
    monkeypatch.setattr(
        import_latest_enriched_csv.subprocess,
        "run",
        lambda cmd, **_kwargs: calls.append(cmd),
    )

    assert import_latest_enriched_csv.main() == 0
    assert len(calls) == 1
    assert "--dry-run" in calls[0]
