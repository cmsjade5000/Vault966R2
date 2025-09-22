import os
import pathlib
import sys
from collections.abc import Generator
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("ADMIN_TOKEN", "testtoken")

from api.db import Base, get_db
from api.main import app
from api.models.movie import Genre, Mood, Movie
from api.models.person import Role  # noqa: F401 - ensure mapper registration


def _get_or_create(session: Session, model, name: str):
    instance = session.query(model).filter(model.name == name).one_or_none()
    if instance is None:
        instance = model(name=name)
        session.add(instance)
        session.flush()
    return instance


def _create_movie(
    session: Session,
    *,
    title: str,
    year: int,
    runtime: int,
    imdb_id: str,
    tmdb_id: int,
    genres: List[str],
    moods: List[str],
) -> None:
    genre_objs = [_get_or_create(session, Genre, name) for name in genres]
    mood_objs = [_get_or_create(session, Mood, name) for name in moods]

    movie = Movie(
        title=title,
        year=year,
        runtime=runtime,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        genres=genre_objs,
        moods=mood_objs,
    )
    session.add(movie)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        _create_movie(
            session,
            title="Blade Runner",
            year=1982,
            runtime=117,
            imdb_id="tt0083658",
            tmdb_id=78,
            genres=["Sci-Fi"],
            moods=["Moody"],
        )
        _create_movie(
            session,
            title="The Matrix",
            year=1999,
            runtime=136,
            imdb_id="tt0133093",
            tmdb_id=603,
            genres=["Sci-Fi", "Action"],
            moods=["Exciting"],
        )
        _create_movie(
            session,
            title="Toy Story",
            year=1995,
            runtime=81,
            imdb_id="tt0114709",
            tmdb_id=862,
            genres=["Animation"],
            moods=["Family"],
        )
        for idx in range(30):
            _create_movie(
                session,
                title=f"Movie {idx:02d}",
                year=2000 + (idx % 5),
                runtime=90 + idx,
                imdb_id=f"ttmovie{idx:02d}",
                tmdb_id=1000 + idx,
                genres=["Library"],
                moods=["General"],
            )
        session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"Authorization": "Bearer testtoken"}
