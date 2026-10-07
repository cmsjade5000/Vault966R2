# Dependency compatibility validation — October 7, 2026

Base: `103a3d1f37d766bcbf5e48f87196437386de0cb3` (`public-main`).
This branch adds validation only. Production dependency requirements are unchanged.
No Dependabot approval, merge, or deployment has been performed.

## Local evidence

- Python 3.12; isolated Linux environment.
- Uvicorn 0.54.0: four real-socket tests pass, covering direct/trusted proxy behavior,
  mixed-case connection-close tokens, WebSocket survival past HTTP keep-alive, and shutdown.
- Alembic 1.20.0: SQLite migration and existing constraint tests pass (four tests).
- Combined current targets (Uvicorn 0.54.0, psycopg/binary 3.3.6, Alembic 1.20.0,
  SQLAlchemy 2.1.1): 634 passed, one skipped, one xfailed; three deprecation warnings.
- Refreshed combined stack with SQLAlchemy 2.1.3: also 634 passed, one skipped,
  one xfailed, three warnings; dependency consistency check passed.
- JavaScript: 77 passed.
- Dependency consistency: `uv pip check` passed for the current combined targets.
- Black, Ruff, whitespace checks pass for the new tests; workflow YAML parses.
- A first run failed because this execution environment configures a SOCKS proxy
  without socksio installed. Installing the optional environment dependency fixed
  the affected existing test. This is not a proposed production dependency change.

## Added coverage

- Real Uvicorn subprocess and socket tests, using a synthetic ASGI app.
- PostgreSQL temporary-table JSON/timestamp round-trip, unique constraint failure,
  rollback/reuse, and prepared-statement reset after DEALLOCATE ALL.
- Real SQLite migration replay through a historical revision, synthetic data insertion,
  upgrade to head, integrity/foreign-key checks, unique/index preservation, and a
  latest-revision downgrade/upgrade round trip.
- CI comparison matrix: baseline, then cumulative Uvicorn, psycopg, Alembic,
  SQLAlchemy 2.1.1, and SQLAlchemy 2.1.3 targets. All jobs use a disposable
  PostgreSQL 16/pgvector service, explicitly require the driver test database,
  report resolved versions/libpq, and replay PostgreSQL migrations.

## Remaining approval gates

PostgreSQL is unavailable locally. Its new tests and migration replay have not run.
The CI workflow must be pushed and exercised before claiming PostgreSQL compatibility.
A passing synthetic driver test does not establish PostgreSQL application CRUD,
relationship loading, pgvector query behavior, enum reflection, or autogenerate parity.
Those remain follow-up coverage if the initial matrix is green.

The SQLite migration check uses generated data and does not certify every historical
user database. The HTTP tests use a synthetic app; actual Vault startup/login/static
routes through a real server and macOS/iPad acceptance remain separate checks.

Known warnings concern Starlette's httpx TestClient deprecation and the older HTTP
422 constant. They were visible, not suppressed.

Recommended merge order remains Uvicorn, psycopg, Alembic, SQLAlchemy, with fresh
checks on the updated base after each merge. Keep SQLAlchemy separate and review the
2.1.3 refresh before changing #273. This report grants no merge or deployment approval.
