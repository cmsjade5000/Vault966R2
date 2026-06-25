# Codex Runbook

This runbook is the handoff surface for Codex sessions working in Vault 966.

## Start Every Task

1. Read `AGENTS.md`.
2. Run `git status --short` and keep unrelated changes separate.
3. Treat this repository as source and `~/Library/Application Support/Vault966/app`
   as the deployed copy.
4. Preserve `.env`, database files, logs with user data, and credentials.

## Skills

Project skills live in `skills/` and are exposed to Codex through
`.agents/skills` symlinks. Use them when the task matches their description:

- `metadata-cleanup`: flagged movie metadata corrections.
- `poster-backdrop-audit`: artwork coverage and replacement review.
- `movie-import-review` or `csv-import-guard`: imports and CSV validation.
- `duplicate-resolution`: duplicate movie detection and merge planning.
- `database-health-check`: collection anomaly audits.
- `test-suite-runner`: full test execution summaries.
- `vault-security-audit`: security scan summaries.

For contributor-facing examples and expected outputs, see
[Codex Skill Examples](codex-skill-examples.md).

## Verification Commands

Use these Make targets instead of assembling ad hoc command sequences:

```bash
make codex.status
make codex.check
make codex.full
make codex.live
```

- `codex.status` prints git state, Codex skill links, and service status.
- `codex.check` runs the default quick verification suite.
- `codex.full` runs Python lint, JS lint, Python tests, and JS tests.
- `codex.live` restarts the deployed macOS service and checks live HTTP routes.

Run focused tests while iterating, then use the narrowest target that proves the
changed behavior. For shared application changes, finish with `make codex.live`.

## Live Service Contract

The iPad uses the deployed app under
`~/Library/Application Support/Vault966/app`, not the repository checkout.
After Python, template, CSS, JavaScript, config, or dependency changes:

1. Run `scripts/vault_service.sh restart` or `make codex.live`.
2. Verify the affected route or asset through `http://127.0.0.1:8000`.
3. Do not edit the deployed app directly unless recovering the service.

## Noisy Artifacts

Ignore generated caches and local runtime artifacts. If duplicate Finder-style
files appear, such as `name 2.js` or `test_name 2.py`, confirm they are not
intentional before deleting them. Do not remove unrelated files from a dirty
worktree without explicit user approval.
