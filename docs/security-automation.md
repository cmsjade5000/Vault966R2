# Security Automation

Vault966 uses a small set of GitHub-side checks to catch dependency and source
risks before they become release work.

## CodeQL

The `Security` workflow runs CodeQL for Python and JavaScript/TypeScript on a
weekly schedule, on manual dispatch, and on pull requests that touch application
code, templates, scripts, dependency manifests, or the workflow itself.

CodeQL findings are uploaded to GitHub code scanning through the repository's
security events permission. Review findings in GitHub Security, then patch and
verify them locally before merging.

## Dependabot

Dependabot is configured in `.github/dependabot.yml` for Python, npm, and GitHub
Actions dependencies. Treat dependency PRs as normal code changes: review the
changelog, run focused tests for the affected area, and use the full Codex check
wrapper before merge when behavior could change.

## Local Audits

Use the `vault-security-audit` Codex project skill when a change needs a local
security sweep. It runs the configured static and dependency scanners and
summarizes remediation steps without exposing private database contents or
secrets.
