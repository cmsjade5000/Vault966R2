# Repository Guide for Agents

This file is a quick orientation for maintaining context when the CLI session resets. It highlights the primary folders and what lives in them so you can reopen only what you need.

## Quick Commands & APIs
- Run API: `make dev` (alias: `make devserver`; loads `.env.local` or `.env` if present and pipes logs through `jq`)
- Tests: `python3 -m pytest`
- JS lint (after `npm install`): `npm run lint`
- `GET /ui/movies` renders `templates/movies_grid.html`
- `GET /movies/{id}/detail` returns `MovieDetail` (edit drawer data)
- `PATCH /movies/{id}` accepts `MovieUpdate` (metadata + optional `resolve_flag`)
- `POST/DELETE /movies/{id}/flag`, `GET /movies/flags` manage the flag queue
- Admin endpoints require `Authorization: Bearer <ADMIN_TOKEN>`; for UI admin actions (manual add,
  collection health refresh) set `localStorage.vaultAdminToken` in the browser.

## Top-Level Map
- **api/** – FastAPI backend. Key subfolders:
  - `routers/` (HTTP endpoints: movies, ui, picks, manual add, etc.)
  - `services/` (business logic such as detail assembly, curation, lookups)
  - `models/` (SQLAlchemy models, incl. `movie.py` and `movie_flag.py`)
  - `schemas/` (Pydantic DTOs returned/accepted by the API)
  - `utils/` (shared helpers e.g. pagination, provider merging)
- **templates/** – Jinja HTML templates. `movies_grid.html` drives `/ui/movies` and includes partials for cards, tables, edit dialog, etc.
- **static/** – Front-end assets. `css/movies.css` holds shared movie styling; focused modules such as `js/library_page.js`, `js/movie_preferences.js`, `js/movie_detail.js`, and `js/movie_detail_edit.js` own page behavior.
- **core/** – Domain utilities (genre normalization, poster theme selection, picker scoring) plus this guide.
- **tests/** – Pytest suite covering API endpoints and service helpers (`test_movie_search`, `test_movie_flags`, etc.).
- **scripts/** – One-off or legacy ETL utilities (manual importers, TMDb enrichment, asset generation).
- **data/** – CSV exports/imports for the library (enriched metadata, skips, etc.).
- **docs/** – Markdown documents (feature matrix, samples) used for project notes.

- Editing metadata flows touch `api/routers/movies.py`, `api/schemas/movie.py`, `templates/movie_detail.html`, and `static/js/movie_detail_edit.js`.
- Flagging lives in `api/models/movie_flag.py`, the `PATCH /movies/{id}` + flag endpoints, and the card/table controls in the templates/JS.
- Filter parsing and DB filtering live in `core/movie_filters.py`; both REST and UI routes reuse it.
- `MovieFlag` cascades on delete; `MovieUpdate.where_to_watch` expects a provider list but is stored `;`-joined after `merge_providers`.
- Run `test_movie_flags` and `test_movie_search` after changing metadata/flag behavior.

Use this index to jump straight to the relevant files instead of re-opening everything after a restart.
