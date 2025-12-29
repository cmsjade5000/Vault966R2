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

## Linters and formatting
- `npm run lint` (Prettier check for `static/js/**/*.js`)
- `npm run fmt` (Prettier write for `static/js/**/*.js`)

## Conventions
- Python: follow existing FastAPI/SQLAlchemy/Pydantic patterns; keep names `snake_case`.
- JavaScript: keep formatting compliant with Prettier and avoid inline scripts/styles to preserve CSP.
