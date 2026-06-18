## Project map
- `api/`: FastAPI routes, dependencies, schemas, services, and database models.
- `templates/`: Jinja templates for the server-rendered UI.
- `static/`: CSS, JavaScript, images, and PWA assets.
- `core/`: Shared movie-domain and filtering utilities.
- `tests/`: Python tests, with browser-side JavaScript tests under `tests/js/`.
- `scripts/`: Service management, imports, backfills, audits, and maintenance tools.
- `data/`: Import inputs and local data artifacts; do not expose database contents or secrets.
- `docs/`: Product and maintenance documentation.
- `reports/`: Generated audits and benchmark outputs.
- `client_py/` and `client_ts/`: Generated or maintained API clients.
- `legacy/`: Legacy ETL and compatibility code; avoid expanding it unless the task requires it.

## Working boundaries
- Treat the repository root as the source tree.
- Treat `~/Library/Application Support/Vault966/app` as a deployed copy, not a second source tree.
- The live SQLite database is `~/Library/Application Support/Vault966/data/vault.db`; preserve it and avoid destructive or bulk data changes unless the user explicitly requests them.
- Never copy `.env` values, database contents, logs containing user data, or credentials into chat, reports, fixtures, or commits.
- Keep generated caches, virtual environments, `node_modules`, service logs, and database backups out of version control.

## Review guidelines
- Avoid logging personally identifiable information (PII).
- Verify every route is wrapped in authentication/authorization middleware; explicitly document public endpoints.
- Enforce strict input validation using whitelists and length limits; reject unexpected input early.
- Encode user-controlled data when rendering output to HTML/JavaScript; avoid `innerHTML`/`dangerouslySetInnerHTML` and do not mark template output as safe unless sanitized.
- Avoid reflecting untrusted data back to the user; keep the contract as restrictive as possible.
- Use appropriate security headers (Content-Type, X-Content-Type-Options, CSP).
- Prefer parameterized queries/ORM filters; never concatenate user input into raw SQL.
- Prevent open redirects by allowing only known internal paths.

## Tests
- `pytest`
- Run focused tests while iterating, then run the full suite before completion when the change can affect shared behavior.

## Live iPad service
- The iPad uses the deployed macOS service under `~/Library/Application Support/Vault966/app`, not the repository working tree.
- After any application change (Python, templates, static CSS/JavaScript, configuration, or dependencies), run `scripts/vault_service.sh restart`.
- Do not report the work complete until the restart succeeds and the affected live route or asset has been verified through `http://127.0.0.1:8000`.

## Linters and formatting
- `npm run lint` (Prettier check for `static/js/**/*.js`)
- `npm run fmt` (Prettier write for `static/js/**/*.js`)

## Conventions
- Python: follow existing FastAPI/SQLAlchemy/Pydantic patterns; keep names `snake_case`.
- JavaScript: keep formatting compliant with Prettier and avoid inline scripts/styles to preserve CSP.
- Prefer existing project modules and patterns over adding new top-level folders or dependencies.
