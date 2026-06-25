---
name: vault-security-audit
description: Run security scanners (Bandit for Python, npm audit for frontend) and static analysis on the codebase, then summarize vulnerabilities and remediation steps. Use when asked to audit, scan, or report security issues.
---

# Vault Security Audit

## Goal
Run Python and frontend security scans, collect findings, and produce a concise remediation summary.

## Workflow
1. Identify languages and tools in the repo (Python, Node).
2. Run scanners deterministically.
3. Capture raw outputs.
4. Summarize by severity, include file/line when available.
5. Propose fixes and confirm before applying changes.

## Scanners
- Python: `bandit -r api core tests scripts`
- Frontend: `npm audit --production`
- Optional static analysis if configured: `ruff`, `pip-audit`, `semgrep` (only if present in the repo or requested).

## Notes
- If a scanner is missing, ask to install it or provide a fallback (e.g., `pip-audit`).
- Prefer report formats that include line numbers (`bandit -f json` + summarize).
- Keep output concise: top issues first, avoid dumping full logs unless asked.

## Output format
- **Findings**: ordered by severity; include file and line.
- **Risk**: brief impact statement.
- **Fix**: concrete change or dependency upgrade.

Example summary line:
- High: `api/utils/omdb.py:42` uses `requests` without timeout; add a timeout to prevent hanging.
