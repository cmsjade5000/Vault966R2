import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_postgres_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.xfail("Postgres DATABASE_URL not configured")

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar_one()
            assert result == 1
    finally:
        engine.dispose()
