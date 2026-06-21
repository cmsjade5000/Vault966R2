# vault966-r2 (FastAPI skeleton)

This is the starter scaffold for migrating Vault 966 from Streamlit to a real API.
- **FastAPI** backend now, optional **Next.js** frontend later.
- **SQLite** by default for easy local start; flip to **Postgres** with `DATABASE_URL`.

Start with [PROJECT.md](PROJECT.md) for the current project map, source/deployment
boundaries, documentation index, and maintenance workflow.
For Codex-specific workflow guidance, use [AGENTS.md](AGENTS.md) and
[docs/codex-runbook.md](docs/codex-runbook.md).

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

Visit http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs

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
- Admin-only endpoints include movie/person creation, role attachments, manual add, and collection
  health refresh. For UI buttons that call admin endpoints (e.g., collection health refresh), set
  `localStorage.vaultAdminToken = "<ADMIN_TOKEN>"` in your browser console to attach the header.

## Meet Flic

- **Fliclists**: save picker presets from `/ui/movies` (tap “Save current filters”) and replay them from the chip row; they’re exposed via `/fliclists`.
- **Flic Score**: `/movies/picks` ranks candidates with runtime/genre hints; search can opt into the same ordering with `order_by=flic`.
- **Flic Memory**: every pick goes into a 10-item history (`/fliclists/history`); newest first for quick revisits.

Tip: Build a themed Fliclist (runtime, decade, genre), flip to Flic Score ordering, and check `/fliclists/history` to see your recent queue.

## Postgres via Docker Compose

```bash
cp .env.example .env  # updates DATABASE_URL to use Postgres
make db.up            # start pgvector-enabled postgres in docker

# once the container reports healthy, run migrations
make db.migrate

# optional: seed a few movies
python scripts/etl_postgres.py

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

The `/ui/movies` page includes a "Semantic search" toggle. The API endpoint is
`POST /api/search/semantic` (falls back to keyword search if embeddings are unavailable).

## Running migrations manually

1. Ensure the database is running (`make db.up`).
2. Confirm `DATABASE_URL` inside `.env` points at Postgres.
3. Run `make db.migrate` (or `alembic upgrade head`) to apply the latest Alembic revisions.
4. (Optional) Seed data with `python scripts/etl_postgres.py`.

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
step uses `npx openapi-typescript`, so ensure Node.js is installed locally. CI
pins `openapi-python-client` to the same generator version used by the drift
gate.

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

## Next steps
- Put your existing picker/filter logic into `core/`.
- Archived import utilities live under `legacy/etl/` (see `legacy/etl/etl_seed.py` if you still need the CSV importer).
- Pull richer metadata (posters/genres/providers) with `python legacy/etl/enrich_tmdb.py --output data/enriched_movies.csv` if you still rely on the archived ETL tooling.
- Optional overrides live in `scripts/overrides/imdb_map.csv`; the importer reads them (title/year keyed) before network lookups and logs usages to `reports/overrides_used.csv`.
- Save reusable picker presets (“Fliclists”) from the `/ui/movies` page; they’re stored via the new `/fliclists` API and can be reapplied with one tap.
- `legacy/etl/retry_missing_ids.py` can revisit `reports/missing_imdb_id.csv` / `invalid_imdb_id.csv` and emit a patch file (`--output`) you can replay through the importer once an IMDb ID becomes known.
- When ready, switch to Postgres by setting `DATABASE_URL` in `.env`.
