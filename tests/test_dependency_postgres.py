"""Driver contract against an explicitly supplied disposable PostgreSQL database."""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


@pytest.mark.integration
def test_psycopg_roundtrip_rollback_and_prepared_statement_reset():
    url = os.getenv("DEPENDENCY_TEST_DATABASE_URL")
    if not url:
        if os.getenv("REQUIRE_DEPENDENCY_POSTGRES") == "1":
            pytest.fail("DEPENDENCY_TEST_DATABASE_URL is required for this job")
        pytest.skip("Disposable dependency PostgreSQL database not configured")
    assert url.startswith("postgresql+psycopg://")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.dialect.driver == "psycopg"
            conn.execute(
                text(
                    "CREATE TEMP TABLE dependency_probe "
                    "(id integer PRIMARY KEY, payload jsonb, stamp timestamptz)"
                )
            )
            stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
            conn.execute(
                text("INSERT INTO dependency_probe VALUES " "(1, CAST(:payload AS jsonb), :stamp)"),
                {"payload": '{"items": [1, null, "test"]}', "stamp": stamp},
            )
            conn.commit()
            row = conn.execute(text("SELECT payload, stamp FROM dependency_probe")).one()
            assert row.payload == {"items": [1, None, "test"]}
            assert row.stamp == stamp
            conn.commit()
            with pytest.raises(IntegrityError):
                conn.execute(text("INSERT INTO dependency_probe (id) VALUES (1)"))
            conn.rollback()
            assert conn.execute(text("SELECT count(*) FROM dependency_probe")).scalar_one() == 1
            conn.commit()
            raw = conn.connection.driver_connection
            for _ in range(7):
                assert raw.execute("SELECT %s::integer", (42,), prepare=True).fetchone() == (42,)
            raw.execute("DEALLOCATE ALL")
            assert raw.execute("SELECT %s::integer", (42,), prepare=True).fetchone() == (42,)
            raw.rollback()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_vault_relationships_enum_and_schema_roundtrip():
    """Use Vault mappings inside a rolled-back, uniquely named schema."""
    from uuid import uuid4

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import MetaData, delete, inspect, select
    from sqlalchemy.orm import Session, selectinload

    from api.models.movie import Genre, Mood, Movie, movie_genres, movie_moods
    from api.models.person import Person, Role, RoleType

    url = os.getenv("DEPENDENCY_TEST_DATABASE_URL")
    if not url:
        if os.getenv("REQUIRE_DEPENDENCY_POSTGRES") == "1":
            pytest.fail("DEPENDENCY_TEST_DATABASE_URL is required for this job")
        pytest.skip("Disposable dependency PostgreSQL database not configured")
    assert url.startswith("postgresql+psycopg://")
    engine = create_engine(url)
    schema = "dependency_" + uuid4().hex
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            default_schema = conn.dialect.default_schema_name
            try:
                conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
                conn.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
                conn.dialect.default_schema_name = schema
                tables = [
                    Movie.__table__,
                    Genre.__table__,
                    Mood.__table__,
                    Person.__table__,
                    movie_genres,
                    movie_moods,
                    Role.__table__,
                ]
                metadata = MetaData()
                for table in tables:
                    table.to_metadata(metadata)
                metadata.create_all(conn)
                with Session(
                    bind=conn, autoflush=False, join_transaction_mode="create_savepoint"
                ) as session:
                    movie = Movie(
                        title="Postgres fixture",
                        runtime=99,
                        genres=[Genre(name="Test genre")],
                        moods=[Mood(name="Test mood")],
                    )
                    person = Person(name="Test performer")
                    session.add_all([movie, person])
                    session.flush()
                    movie.roles.append(Role(person=person, role_type=RoleType.ACTOR))
                    session.commit()
                    movie_id = movie.id
                    session.expunge_all()
                    loaded = session.scalars(
                        select(Movie)
                        .where(Movie.id == movie_id)
                        .options(
                            selectinload(Movie.genres),
                            selectinload(Movie.moods),
                            selectinload(Movie.roles),
                        )
                    ).one()
                    assert [g.name for g in loaded.genres] == ["Test genre"]
                    assert [m.name for m in loaded.moods] == ["Test mood"]
                    assert loaded.roles[0].role_type is RoleType.ACTOR
                    loaded.title = "Updated fixture"
                    session.commit()
                    session.expire_all()
                    assert session.get(Movie, movie_id).title == "Updated fixture"
                    session.execute(delete(Movie).where(Movie.id == movie_id))
                    session.commit()
                    assert session.scalar(select(Movie.id).where(Movie.id == movie_id)) is None
                enums = {e["name"]: e["labels"] for e in inspect(conn).get_enums(schema=schema)}
                assert enums["roletype"] == ["ACTOR", "DIRECTOR", "WRITER"]
                context = MigrationContext.configure(conn)
                assert compare_metadata(context, metadata) == []
            finally:
                transaction.rollback()
                conn.dialect.default_schema_name = default_schema
    finally:
        engine.dispose()
