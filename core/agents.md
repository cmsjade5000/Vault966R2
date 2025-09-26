# Repository Guide for Agents

This file is a quick orientation for maintaining context when the CLI session resets. It highlights the primary folders and what lives in them so you can reopen only what you need.

## Quick Commands & APIs
- Run API: `uvicorn api.main:app --reload`
- Tests: `python3 -m pytest`
- JS lint (after `npm install`): `npm run lint`
- `GET /ui/movies` renders `templates/movies_grid.html`
- `GET /movies/{id}/detail` returns `MovieDetail` (edit drawer data)
- `PATCH /movies/{id}` accepts `MovieUpdate` (metadata + optional `resolve_flag`)
- `POST/DELETE /movies/{id}/flag`, `GET /movies/flags` manage the flag queue

## Top-Level Map
- **api/** – FastAPI backend. Key subfolders:
  - `routers/` (HTTP endpoints: movies, ui, picks, manual add, etc.)
  - `services/` (business logic such as detail assembly, curation, lookups)
  - `models/` (SQLAlchemy models, incl. `movie.py` and `movie_flag.py`)
  - `schemas/` (Pydantic DTOs returned/accepted by the API)
  - `utils/` (shared helpers e.g. pagination, provider merging)
- **templates/** – Jinja HTML templates. `movies_grid.html` drives `/ui/movies` and includes partials for cards, tables, edit dialog, etc.
- **static/** – Front-end assets. `css/movies.css` and `js/movies_page.js` hold the styling/behavior for the movie grid, filters, flags, and edit drawer.
- **core/** – Domain utilities (genre normalization, poster theme selection, picker scoring) plus this guide.
- **tests/** – Pytest suite covering API endpoints and service helpers (`test_movie_search`, `test_movie_flags`, etc.).
- **scripts/** – One-off or legacy ETL utilities (manual importers, TMDb enrichment, asset generation).
- **data/** – CSV exports/imports for the library (enriched metadata, skips, etc.).
- **docs/** – Markdown documents (feature matrix, samples) used for project notes.

- Editing metadata flows touch `api/routers/movies.py`, `api/schemas/movie.py`, `templates/movies_grid.html`, and `static/js/movies_page.js`.
- Flagging lives in `api/models/movie_flag.py`, the `PATCH /movies/{id}` + flag endpoints, and the card/table controls in the templates/JS.
- Filter logic sits in `api/services/movie_filters.py` (both REST + UI).
- `MovieFlag` cascades on delete; `MovieUpdate.where_to_watch` expects a provider list but is stored `;`-joined after `merge_providers`.
- Run `test_movie_flags` and `test_movie_search` after changing metadata/flag behavior.

Use this index to jump straight to the relevant files instead of re-opening everything after a restart.
