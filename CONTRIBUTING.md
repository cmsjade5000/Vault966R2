# Contributing to Vault 966

Thanks for helping improve Vault 966. This project is public open-source
software, so contribution quality and private-data hygiene matter.

## Start Here

1. Read [README.md](README.md), [PROJECT.md](PROJECT.md), and [AGENTS.md](AGENTS.md).
2. Check `git status --short` before changing files.
3. Keep unrelated work in separate commits or pull requests.
4. Preserve local runtime data: never commit `.env`, databases, logs, local
   backups, credentials, or private movie exports.

## First-Time External Contributors

You do not need collaborator access or issue assignment to contribute. Fork the
repository, create a branch in your fork, and open a pull request that links the
issue you are addressing.

Maintainers may leave beginner-friendly issues unassigned until a pull request
is opened. This keeps repository access limited while still allowing public
contributions.

Before opening a pull request:

- Comment on the issue only if you need clarification.
- Keep the change narrowly scoped to the issue.
- Do not modify GitHub Actions workflows, dependency files, security settings,
  deployment scripts, generated clients, or private-data handling unless the
  issue specifically asks for that work.
- Use synthetic test data only.
- Never ask maintainers for secrets, database files, local logs, production
  paths, or collaborator access.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make dev
```

Visit `http://127.0.0.1:8000/health` to confirm the app is running.

## Project Boundaries

- Source code lives in this repository.
- `~/Library/Application Support/Vault966/app` is a deployed copy, not a second
  source tree.
- The live SQLite database is private runtime state and must not be committed.
- Durable documentation belongs in `docs/`; generated audits and screenshots
  belong in `reports/`.

## Before Opening a Pull Request

Run focused tests while iterating. For shared changes, run the relevant wrapper:

```bash
make codex.check
```

Use broader checks when the change affects shared behavior:

```bash
make codex.full
```

Application changes that affect the live iPad service should also be verified
with:

```bash
make codex.live
```

If your change touches one of the recurring maintenance areas, use the matching
project workflow in `skills/` or explain why it does not apply:

- imports and CSV validation
- metadata cleanup and source lookup
- duplicate resolution
- poster/backdrop audits
- database health and flag triage
- security audits, test summaries, and release notes

## Security and Privacy Expectations

- Do not log request bodies, credentials, tokens, private database contents, or
  personally identifying information.
- Keep route inputs restrictive and validated with whitelists, limits, or typed
  schemas.
- Use ORM filters or parameterized queries; do not concatenate user input into
  SQL.
- Encode user-controlled data in templates and JavaScript.
- Document public endpoints and authorization-sensitive changes in the PR.

## Pull Request Checklist

- [ ] The change is scoped to the stated problem.
- [ ] Private data and generated runtime artifacts are not included.
- [ ] Tests or verification commands are listed in the PR.
- [ ] Documentation is updated when behavior, setup, or operations change.
- [ ] Security-sensitive behavior is called out for reviewer attention.
