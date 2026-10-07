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
