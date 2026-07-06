from contextlib import nullcontext
import csv

from api.models.movie import Genre, Mood, Movie
from scripts import backfill_moods


def _get_or_create(db, model, name: str):
    row = db.query(model).filter(model.name == name).one_or_none()
    if row is None:
        row = model(name=name)
        db.add(row)
        db.flush()
    return row


def test_backfill_moods_dry_run_writes_report_without_mutating_db(
    db_session,
    monkeypatch,
    tmp_path,
) -> None:
    genre = _get_or_create(db_session, Genre, "Comedy")
    movie = Movie(
        title="Dry Run Comedy",
        year=2024,
        runtime=96,
        imdb_id="ttdryrun01",
        tmdb_id=910001,
        genres=[genre],
        keywords=["satire"],
        plot="A hilarious comedy about friends in absurd misadventures.",
        moods=[],
    )
    db_session.add(movie)
    db_session.commit()
    mood_count = db_session.query(Mood).count()
    report = tmp_path / "moods.csv"

    monkeypatch.setattr(backfill_moods, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(
        "sys.argv",
        ["backfill_moods.py", "--force", "--report", str(report)],
    )

    assert backfill_moods.main() == 0
    db_session.refresh(movie)

    assert db_session.query(Mood).count() == mood_count
    assert movie.moods == []
    rows = list(csv.DictReader(report.open(encoding="utf-8")))
    planned = [row for row in rows if row["title"] == "Dry Run Comedy"]
    assert planned[0]["action"] == "planned"
    assert planned[0]["computed_moods"] == "Funny"
    assert "keyword:satire" in planned[0]["evidence"]


def test_backfill_moods_apply_force_overwrites_existing_moods(
    db_session,
    monkeypatch,
    tmp_path,
) -> None:
    genre = _get_or_create(db_session, Genre, "Horror")
    legacy_mood = _get_or_create(db_session, Mood, "General")
    movie = Movie(
        title="Fresh Start Horror",
        year=2024,
        runtime=101,
        imdb_id="ttapply01",
        tmdb_id=910002,
        genres=[genre],
        keywords=["haunted house"],
        plot="A family is trapped in a haunted house by a supernatural force.",
        moods=[legacy_mood],
    )
    db_session.add(movie)
    db_session.commit()
    report = tmp_path / "moods.csv"

    class Backup:
        backup = tmp_path / "backup.sqlite"

    monkeypatch.setattr(backfill_moods, "SessionLocal", lambda: nullcontext(db_session))
    monkeypatch.setattr(backfill_moods, "backup_active_sqlite_database", lambda *_, **__: Backup())
    monkeypatch.setattr(
        "sys.argv",
        [
            "backfill_moods.py",
            "--apply",
            "--force",
            "--report",
            str(report),
        ],
    )

    assert backfill_moods.main() == 0
    db_session.refresh(movie)

    assert [mood.name for mood in movie.moods] == ["Scary"]
    rows = list(csv.DictReader(report.open(encoding="utf-8")))
    updated = [row for row in rows if row["title"] == "Fresh Start Horror"]
    assert updated[0]["action"] == "updated"
    assert updated[0]["existing_moods"] == "General"
    assert updated[0]["computed_moods"] == "Scary"
