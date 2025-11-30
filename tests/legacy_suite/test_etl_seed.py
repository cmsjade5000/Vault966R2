import pathlib
import sys

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
TESTS_DIR = PROJECT_ROOT / "tests"
if str(TESTS_DIR) in sys.path:
    sys.path.remove(str(TESTS_DIR))
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))
sys.modules.pop("legacy", None)

from api.models.movie import Movie

try:
    from scripts import etl_seed  # type: ignore
except RuntimeError:  # pragma: no cover - fallback in CI
    from legacy.etl import etl_seed as etl_seed  # type: ignore


@pytest.fixture()
def in_memory_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    etl_seed.Base.metadata.create_all(bind=engine)

    original_session_local = etl_seed.SessionLocal
    monkeypatch.setattr(etl_seed, "SessionLocal", testing_session_local)

    yield testing_session_local

    etl_seed.Base.metadata.drop_all(bind=engine)
    monkeypatch.setattr(etl_seed, "SessionLocal", original_session_local)


def _base_record():
    return {
        "title": "Primer",
        "year": 2004,
        "runtime": 77,
        "plot": "Two engineers accidentally invent a time machine.",
        "poster_url": "https://example.com/primer.jpg",
        "backdrop_url": None,
        "genres": ["Sci-Fi"],
        "moods": ["Mind-bending"],
    }


def test_tmdb_fallback_deduplicates_movies(in_memory_session, tmp_path):
    duplicates_path = tmp_path / "duplicates.csv"

    tmdb_only = {**_base_record(), "imdb_id": None, "tmdb_id": 1125}
    action, reason = etl_seed.process_record(
        tmdb_only,
        dry_run=False,
        duplicates_path=duplicates_path,
    )
    assert action == "inserted"
    assert reason is None

    imdb_enriched = {**_base_record(), "imdb_id": "tt0390384", "tmdb_id": 1125}
    action, reason = etl_seed.process_record(
        imdb_enriched,
        dry_run=False,
        duplicates_path=duplicates_path,
    )
    assert action in {"updated", "skipped"}
    assert reason in {None, "duplicate_db"}

    with in_memory_session() as session:
        movies = session.execute(
            select(Movie).where(Movie.tmdb_id == 1125)
        ).scalars().all()
        assert len(movies) == 1
        assert movies[0].imdb_id == "tt0390384"

        # Ensure no additional rows were created under a different identifier.
        all_movies = session.execute(select(Movie)).scalars().all()
        assert len(all_movies) == 1

