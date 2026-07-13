# Security Policy

Vault 966 is a self-hosted application that may run near private media metadata,
local credentials, and personal usage logs. Treat private runtime data as out of
scope for source control and public discussion.

First-run setup is intentionally public only until the owner profile exists. Open
`/setup` in the Vault browser UI and submit the form from that page: setup POSTs
require a matching browser `Origin` and are rejected when the origin is missing or
does not match the Vault host. After the first successful setup, the route cannot
replace the owner credentials.

## Supported Versions

Security fixes are accepted for the current `public-main` branch. If release
branches are introduced later, this policy should be updated with explicit support
windows.

## Reporting a Vulnerability

Preferred reporting path: GitHub private vulnerability reporting, available from
the repository's Security tab. Please avoid opening public issues that include
exploit details, credentials, private logs, database rows, or other sensitive
data. If the private reporting flow is unavailable, open a minimal public issue
asking for a maintainer contact path, or contact the repository owner through
GitHub.

Include:

- A concise description of the affected behavior.
- Steps to reproduce using synthetic data.
- Impact and affected route, command, or file when known.
- Suggested remediation if available.

Do not include:

- `.env` values, API keys, session tokens, or passwords.
- Local database contents, backups, or private movie exports.
- Logs containing request bodies, profile names, personal identifiers, or local
  network details.

## Security Review Focus

Reviewers should pay special attention to:

- Authentication and authorization on every route.
- Strict input validation and length limits.
- User-controlled data rendered into HTML or JavaScript.
- SQL construction and ORM filtering.
- Open redirects and unsafe URL handling.
- Security headers, content type handling, and CSP compatibility.
- Logging behavior that could expose private data.

## Codex Security Fit

Vault 966 is a good candidate for deeper security review because it combines a
self-hosted authenticated UI, local runtime data, external metadata providers,
OpenAI-compatible embedding calls, generated API clients, import files, and a
macOS service deployment path. Security review should prioritize narrow,
reviewable fixes and avoid bulk data changes unless a maintainer explicitly
approves them.
