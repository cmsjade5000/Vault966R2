# vault966-r2 (FastAPI skeleton)

This is the starter scaffold for migrating Vault 966 from Streamlit to a real API.
- **FastAPI** backend now, optional **Next.js** frontend later.
- **SQLite** by default for easy local start; flip to **Postgres** with `DATABASE_URL`.

## Quickstart

```bash
# from your vault966-r2 folder
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create a local .env (optional)
cp .env.example .env
# Update .env with a strong `ADMIN_TOKEN`

# Run the API
uvicorn api.main:app --reload
```

Visit http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs

### Admin actions

- Set `ADMIN_TOKEN` in `.env` (the example file includes a placeholder).
- In Swagger UI (`/docs`), click the "Authorize" button and enter `Bearer <your token>`.
- Admin-only endpoints include movie/person creation and role attachments.

## Meet Flic

- **Fliclists**: save picker presets from `/ui/movies` (tap “Save current filters”) and replay them from the chip row; they’re exposed via `/fliclists`.
- **Flic Score**: `/movies/picks` ranks candidates with runtime/genre hints; search can opt into the same ordering with `order_by=flic`.
- **Flic Memory**: every pick goes into a 10-item history (`/fliclists/history`); newest first for quick revisits.

Tip: Build a themed Fliclist (runtime, decade, genre), flip to Flic Score ordering, and check `/fliclists/history` to see your recent queue.

## Postgres via Docker Compose

```bash
cp .env.example .env  # updates DATABASE_URL to use Postgres
make db.up            # start postgres:16 in docker

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

For the small JavaScript helpers under `static/js/`, install Prettier once and
run the formatter as needed:

```bash
npm install
npm run lint
```

Integration tests that depend on Postgres are marked with
`pytest -m integration`. They will be skipped automatically when a
Postgres `DATABASE_URL` is not configured.

## Generating API clients

```bash
make openapi
```

This command freezes `openapi/openapi.json`, regenerates the Python client in
`client_py/`, and emits TypeScript definitions in `client_ts/`. The TypeScript
step uses `npx openapi-typescript`, so ensure Node.js is installed locally.

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
