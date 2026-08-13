# Vault 966

Vault 966 is a self-hosted movie-library and recommendation system for people
who want a private, inspectable alternative to opaque watch queues. It combines
a FastAPI backend, server-rendered UI, movie metadata workflows, local service
management, generated API clients, and Codex-ready maintenance automation.

The project is built around a practical maintainer loop: import and validate
movie data, enrich metadata, resolve duplicates, audit artwork, review security
posture, ship release notes, and verify self-hosted deployments. Those workflows
are documented so contributors and coding agents can work safely without touching
private data.

- **FastAPI** backend with server-rendered Jinja UI and generated OpenAPI clients.
- **SQLite** for local/self-hosted use, with optional **Postgres** and pgvector.
- **Codex maintainer workflows** for metadata cleanup, import review, duplicate
  resolution, security audits, release notes, and verification.
- **Semantic search** with Postgres, pgvector, and OpenAI-compatible embeddings.
- **Private-data boundaries** that keep local databases, logs, and secrets out of
  source control.

Start with [PROJECT.md](PROJECT.md) for the current project map, source/deployment
boundaries, documentation index, and maintenance workflow.
For Codex-specific workflow guidance, use [AGENTS.md](AGENTS.md) and
[docs/codex-runbook.md](docs/codex-runbook.md).
For the Codex for Open Source application narrative, see
[docs/codex-for-oss.md](docs/codex-for-oss.md).
For contributor-friendly next steps, see [ROADMAP.md](ROADMAP.md). For safe
public examples, see [docs/demo-data.md](docs/demo-data.md).
For the supported lifecycle of archived import tooling, see
[docs/legacy-etl.md](docs/legacy-etl.md).
The public repository is
[`cmsjade5000/Vault966R2`](https://github.com/cmsjade5000/Vault966R2), with
`public-main` as the default branch.

## Repository status

Vault 966 is public open-source software maintained from the `public-main`
branch. The repository is ready for contributor review and still keeps local
runtime data out of source control:

- Keep generated logs, databases, credentials, local backups, private import
  snapshots, and generated collection reports out of commits.
- Use synthetic data for public examples, screenshots, tests, and issue
  reproduction.
- Confirm repository metadata, templates, security policy, and maintainer docs
  stay aligned as public workflows evolve.

## Quickstart

```bash
# from your vault966-r2 folder
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create a local .env (optional)
cp .env.example .env
# Update .env with a strong `ADMIN_TOKEN`
# Optional: set `TMDB_API_KEY` / `OMDB_API_KEY` for lookup + enrichment endpoints.

# Run the API
make dev          # alias: make devserver; uses .env.local (or .env fallback) automatically
```

Visit http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs.
`/health`, `/livez`, `/readyz`, `/docs`, `/redoc`, `/openapi.json`, `/login`,
`/logout`, and `/static/*` are intentionally public; application data routes
require a login session or admin bearer token. `/livez` reports process-only
liveness without accessing the database. `/readyz` performs a bounded database
readiness check and returns HTTP 503 when the database is unavailable.

### Always-on Mac Mini service

For the home Mac Mini, install the native macOS background service:

```bash
scripts/vault_service.sh install
scripts/vault_service.sh status
```

The service starts at login, is restarted by macOS if it exits, and checks `/health`
every 30 seconds. Three consecutive failed checks cause a clean restart. A separate
launchd watchdog checks health every minute and force-restarts the complete service
after repeated failures. A daily maintenance job creates a validated online SQLite
backup at 3:30 AM and keeps the newest seven. Vault runs Uvicorn without development
reload. The deployed application, canonical SQLite database, Python environment,
backups, and logs live under
`~/Library/Application Support/Vault966`; the repository's `vault.db` links to that
same database so local maintenance tools continue to operate on the live data.

The current service is a per-user LaunchAgent, so it cannot start after a reboot
until that user logs in. Automatic unattended power-outage recovery also requires
the macOS restart-after-power-failure setting and, while FileVault remains enabled,
an authorized disk unlock after a full shutdown. See
[Power-Outage Recovery](docs/power-outage-recovery.md) for the current limitation,
recommended architecture, recovery commands, backup checks, and quarterly drill.

The iPad always uses this deployed copy, not files directly from the repository.
Run `scripts/vault_service.sh restart` after every application change, including
Python, templates, static CSS/JavaScript, configuration, and dependencies. The
command waits for the live `/health` endpoint before reporting success. Use
`scripts/vault_service.sh logs` to follow logs, and
`scripts/vault_service.sh uninstall` to remove the service. Double-clicking
`Launch Vault 966.command` installs or refreshes the service and opens the login page.

### Admin actions

- Set `ADMIN_TOKEN` in `.env` (the example file includes a placeholder).
- In Swagger UI (`/docs`), click the "Authorize" button and enter `Bearer <your token>`.
- Admin-only API endpoints include movie/person creation, role attachments,
  direct Fliclist writes, and collection health refreshes.
- The live UI uses profile sessions and same-origin form/API requests for
  admin actions such as Vault Health, manual add, source sync, review, and flag
  management.

## Live app surface

The deployed server-rendered app currently exposes:

- `/ui/movies`: searchable movie library with grid/list views, filters, sorting,
  random picks, likes, watchlist actions, and review flags.
- `/ui/movies/{id}`: movie detail pages with poster/backdrop artwork, metadata,
  trailer links when available, preferences, and admin edit/flag controls.
- `/ui/watchlist`: saved watchlist view.
- `/ui/movies/health`: admin Vault Health dashboard with metadata maintenance,
  review workbench, source synchronization, manual add, and snapshot history.
- `/ui/first-import`: first-import staging flow for an empty library.

## Postgres via Docker Compose

```bash
cp .env.example .env  # updates DATABASE_URL to use Postgres
make db.up            # start pgvector-enabled postgres in docker

# once the container reports healthy, run migrations
make db.migrate

# optional: seed a few movies through the archived-but-supported ETL importer
python legacy/etl/etl_seed.py --path legacy/etl/samples/sample_movies.json --format json

# tear everything down when done
make db.down
```

`make db.reset` will drop and recreate the `vault966` database inside the
container before running migrations again. The command is limited to the
database defined by `POSTGRES_DB` (default `vault966`).

## Semantic search (pgvector + OpenAI)

Semantic search runs server-side only and requires Postgres + pgvector.

1) Configure `.env`:
   - `LLM_API_KEY=...` (server-side only)
   - `LLM_EMBEDDING_MODEL=text-embedding-3-small`
   - `LLM_EMBEDDING_DIM=1536` (must match the migration)
   - `SEMANTIC_SEARCH_ENABLED=true`

2) Run migrations (adds `pgvector`, `movie_documents`, and `ai_cache`):

```bash
make db.migrate
```

3) Backfill embeddings (resumable batches):

```bash
python scripts/backfill_semantic_documents.py --limit 500
python scripts/backfill_semantic_documents.py --after-id 500
```

The API endpoint is `POST /api/search/semantic` and falls back to keyword search
if embeddings are unavailable. The current live `/ui/movies` page does not show
a semantic-search toggle.

## Running migrations manually

1. Ensure the database is running (`make db.up`).
2. Confirm `DATABASE_URL` inside `.env` points at Postgres.
3. Run `make db.migrate` (or `alembic upgrade head`) to apply the latest Alembic revisions.
4. (Optional) Seed data through the archived-but-supported ETL importer with `python legacy/etl/etl_seed.py --path legacy/etl/samples/sample_movies.json --format json`.

## Testing

```bash
make fmt     # auto-format with Black + Ruff
make lint    # static analysis
make test    # runs pytest
```

Codex sessions should prefer the project verification wrappers:

```bash
make codex.status
make codex.check
make codex.full
make codex.live
```

For the small JavaScript helpers under `static/js/`, install Prettier once and
run the formatter as needed:

```bash
npm install
npm run lint
```

Integration tests that depend on Postgres are marked with
`pytest -m integration`. They will be skipped automatically when a
Postgres `DATABASE_URL` is not configured.

## Contributing

Contributions should start with [CONTRIBUTING.md](CONTRIBUTING.md). The short
version:

- Do not commit `.env` files, local databases, logs, backups, or private movie
  data exports.
- Use existing project folders and patterns instead of adding new top-level
  areas.
- Run focused tests while iterating and the relevant Codex verification target
  before asking for review.
- Document any public endpoint, data import behavior, or security-sensitive
  change in the PR.
- Use synthetic files under `data/samples/` for public reproduction cases,
  screenshots, or import examples.

## Maintainer automation

Vault 966 includes repo-scoped Codex skills under `skills/` and discoverable
links under `.agents/skills/`. These workflows turn recurring maintenance work
into repeatable review surfaces:

- CSV import validation and movie import review.
- Metadata cleanup, genre/mood normalization, and duplicate resolution.
- Poster/backdrop coverage audits.
- Database health checks and flag triage.
- Security scanning and test-suite summaries.
- Release note drafting.

The same workflow surface is used for local maintenance and public
open-source collaboration. See [docs/codex-for-oss.md](docs/codex-for-oss.md)
for how API credits and Codex access support PR review, maintainer
automation, release workflows, and security coverage.

## Debugging and observability

- Each request gets an `X-Request-ID` (client-supplied or generated) and the same value is echoed in responses.
- Structured JSON logs (`vault966` logger) include method, path, status, duration, and `request_id`. Tail them while debugging: `make dev` (pipes through `jq` for readability).
- Errors return JSON with `error_code`, `message`, and `request_id`, making it easy to correlate with logs without exposing request bodies.

## Generating API clients

```bash
make openapi
```

This command freezes `openapi/openapi.json`, regenerates the Python client in
`client_py/`, and emits TypeScript definitions in `client_ts/`. The TypeScript
step uses the pinned `openapi-typescript` dev dependency, so run `npm install`
before regenerating clients. CI pins both client generators through the Python
environment and `package-lock.json`.

To verify the committed OpenAPI schema and generated clients are up to date,
run:

```bash
make openapi.check
```

## Running everything in Docker

```bash
make app.up
# API available on http://127.0.0.1:8000, Postgres on 5432

# when finished
make app.down
```

The API container mounts the project directory for live code edits and uses the
same `.env` values (including `ADMIN_TOKEN`). The database connection is
configured automatically to talk to the Postgres container.

## Legacy ETL maintenance

`legacy/etl/` is archived-but-supported maintenance code. It is kept for
historical CSV/JSON imports, TMDb enrichment, retry files, samples, and recovery
tasks used by maintainer scripts. New import features should prefer modern
scripts under `scripts/` and shared validation in `core/`, but compatibility and
data-safety fixes may still touch `legacy/etl/`.

Active callers are intentionally allowed to use the legacy importer while this
lifecycle remains supported:

- `scripts/import_latest_enriched_csv.py` calls `legacy/etl/etl_seed.py`.
- `scripts/enriched_csv_orchestrator.py` can call `legacy/etl/enrich_tmdb.py`
  and delegates final import to `scripts/import_latest_enriched_csv.py`.

Tests under `tests/legacy/` and the public samples under `legacy/etl/samples/`
are retained to protect this supported maintenance path. If the legacy ETL is
retired later, remove or replace the callers, tests, samples, and docs in one
coordinated change. See [docs/legacy-etl.md](docs/legacy-etl.md) for the full
support contract.

## Next steps
- Archived-but-supported import utilities live under `legacy/etl/` (see `legacy/etl/etl_seed.py` if you still need the CSV importer).
- Pull richer metadata (posters/genres/providers) with `python legacy/etl/enrich_tmdb.py --output data/enriched_movies.csv` if you still rely on the supported legacy ETL tooling.
- Optional overrides live in `legacy/etl/overrides/imdb_map.csv`; the importer reads them (title/year keyed) before network lookups and logs usages to `reports/overrides_used.csv`.
- `legacy/etl/retry_missing_ids.py` can revisit `reports/missing_imdb_id.csv` / `invalid_imdb_id.csv` and emit a patch file (`--output`) you can replay through the importer once an IMDb ID becomes known.
- When ready, switch to Postgres by setting `DATABASE_URL` in `.env`.
