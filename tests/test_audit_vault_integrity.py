from datetime import datetime, timezone

from api.models.movie import Movie, MovieIngestProvenance
from api.models.movie_review import MovieReviewCheck
from api.models.source_sync import SourceFieldDecision, SourceMovieRow, SourceSnapshot
from api.models.vault_id import RetiredVaultId
from scripts.audit_vault_integrity import _fingerprint, audit


def test_fingerprint_is_stable_and_order_sensitive():
    records = [{"id": 1, "title": "Alien"}, {"id": 2, "title": "Aliens"}]

    assert _fingerprint(records) == _fingerprint(list(records))
    assert _fingerprint(records) != _fingerprint(list(reversed(records)))


def test_audit_separates_approved_source_changes_from_drift(db_session, tmp_path):
    movie = db_session.query(Movie).first()
    movie.vault_id = "V0001"
    movie.runtime = 120
    db_session.add(
        MovieIngestProvenance(
            movie_id=movie.id,
            provider="legacy_vault_csv",
            provider_id=movie.vault_id,
        )
    )
    snapshot = SourceSnapshot(
        filename="new-source.csv",
        file_sha256="a" * 64,
        raw_csv="Title,Time,Director,Year\nBlade Runner,120,Ridley Scott,1982\n",
        row_count=1,
        status="active",
        confirmed_at=datetime.now(timezone.utc),
    )
    db_session.add(snapshot)
    db_session.flush()
    source_row = SourceMovieRow(
        snapshot_id=snapshot.id,
        row_number=2,
        title="Blade Runner",
        normalized_title="blade runner",
        runtime=120,
        director="Ridley Scott",
        normalized_directors=["ridley scott"],
        year=1982,
    )
    db_session.add(source_row)
    db_session.flush()
    db_session.add(
        SourceFieldDecision(
            source_row_id=source_row.id,
            movie_id=movie.id,
            field_name="runtime",
            previous_value="Missing",
            source_value="120",
            selected_value="120",
            decision="use_source",
            decided_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime\nV0001,Blade Runner,1982,\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    assert report["summary"]["approved_source_deviation_count"] == 1
    approved = report["source_reconciliation"]["approved_deviations"]
    assert approved[0]["vault_id"] == "V0001"
    assert approved[0]["differences"]["runtime"]["database"] == 120
    drift = report["source_reconciliation"]["drift"]
    assert "runtime" not in drift[0]["differences"]


def test_audit_accepts_recorded_title_year_authority(db_session, tmp_path):
    movie = db_session.query(Movie).first()
    movie.vault_id = "V0001"
    movie.title = "Blade Runner (1981)"
    movie.year = 1981
    db_session.add(
        MovieIngestProvenance(
            movie_id=movie.id,
            provider="legacy_vault_csv",
            provider_id=movie.vault_id,
        )
    )
    db_session.add(
        MovieReviewCheck(
            movie_id=movie.id,
            issue_type="title_year_conflict",
            issue_fingerprint="a" * 64,
            decision="title_year_applied",
        )
    )
    db_session.commit()

    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime\nV0001,Blade Runner (1981),1982,117\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    approved = report["source_reconciliation"]["approved_deviations"]
    assert approved[0]["differences"]["year"]["database"] == 1981
    assert approved[0]["differences"]["year"]["policy"] == "title_year_authority"
    drift = report["source_reconciliation"]["drift"]
    assert "year" not in drift[0]["differences"]


def test_audit_reports_nonlegacy_movies_as_newer_source_entries(db_session, tmp_path):
    movie = db_session.query(Movie).first()
    movie.vault_id = "V1000"
    db_session.commit()

    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    assert report["summary"]["missing_source_id_count"] == 0
    assert report["summary"]["newer_source_entry_count"] >= 1
    newer = report["source_reconciliation"]["newer_source_entries"]
    assert any(item["vault_id"] == "V1000" for item in newer)


def test_audit_reports_retired_source_ids_separately_from_unmatched_gaps(
    db_session,
    tmp_path,
):
    db_session.add(
        RetiredVaultId(
            vault_id="V0087",
            source="legacy_gap",
            reason="Known legacy Vault ID gap reserved to prevent reuse.",
        )
    )
    db_session.commit()
    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime\n"
        "V0087,Retired Gap,1987,90\n"
        "V0999,Accidental Gap,1999,90\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    assert report["summary"]["retired_vault_id_count"] == 1
    assert report["summary"]["retired_source_vault_id_count"] == 1
    assert report["source_reconciliation"]["source_unmatched_vault_ids"] == ["V0999"]
    retired = report["source_reconciliation"]["retired_source_vault_ids"]
    assert retired[0]["vault_id"] == "V0087"
    assert retired[0]["source"] == "legacy_gap"


def test_audit_reports_added_posters_as_artwork_enrichment(db_session, tmp_path):
    movie = db_session.query(Movie).first()
    movie.vault_id = "V0001"
    movie.poster_url = "https://media.themoviedb.org/t/p/w500/poster.jpg"
    db_session.add(
        MovieIngestProvenance(
            movie_id=movie.id,
            provider="legacy_vault_csv",
            provider_id=movie.vault_id,
        )
    )
    db_session.commit()

    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime,poster_url\n" "V0001,Blade Runner,1982,117,\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    assert report["summary"]["source_drift_count"] == 1
    assert report["summary"]["artwork_enrichment_count"] == 1
    drift = report["source_reconciliation"]["drift"][0]["differences"]
    assert "poster_url" not in drift
    artwork = report["source_reconciliation"]["artwork_enrichments"]
    assert artwork[0]["vault_id"] == "V0001"


def test_audit_accepts_exact_external_id_enrichment(db_session, tmp_path):
    movie = db_session.query(Movie).first()
    movie.vault_id = "V0001"
    movie.imdb_id = "tt0083658"
    movie.tmdb_id = 78
    db_session.add_all(
        [
            MovieIngestProvenance(
                movie_id=movie.id,
                provider="legacy_vault_csv",
                provider_id=movie.vault_id,
            ),
            MovieIngestProvenance(
                movie_id=movie.id,
                provider="omdb",
                provider_id=movie.imdb_id,
                notes="Exact normalized title and exact year; external IDs cross-checked.",
            ),
            MovieIngestProvenance(
                movie_id=movie.id,
                provider="tmdb",
                provider_id=str(movie.tmdb_id),
                notes="Exact normalized title and exact year; external IDs cross-checked.",
            ),
        ]
    )
    db_session.commit()

    source_path = tmp_path / "legacy.csv"
    source_path.write_text(
        "vault_id,title,year,runtime,imdb_id,tmdb_id\n" "V0001,Blade Runner,1982,117,,\n",
        encoding="utf-8",
    )

    report = audit(db_session, source_path=source_path, sample_size=0)

    approved = report["source_reconciliation"]["approved_deviations"][0]["differences"]
    assert approved["imdb_id"]["policy"] == "exact_external_match"
    assert approved["tmdb_id"]["policy"] == "exact_external_match"
    drift = report["source_reconciliation"]["drift"][0]["differences"]
    assert "imdb_id" not in drift
    assert "tmdb_id" not in drift
