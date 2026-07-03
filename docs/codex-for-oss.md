# Codex for Open Source

This document frames Vault 966 for the OpenAI Codex for Open Source program and
keeps the application narrative tied to concrete maintainer work.

The current program page says API credits are intended for projects using Codex
in pull request review, maintainer automation, release workflows, or other core
OSS work. It also calls out day-to-day coding, triage, review, maintainer
workflows, and conditional Codex Security access for repositories that need
deeper security coverage:
<https://developers.openai.com/community/codex-for-oss>

## Project Positioning

Vault 966 is a self-hosted movie-library and recommendation platform with a
strong focus on data quality, private deployment, and repeatable maintenance. It
is useful beyond one household because many personal media collections face the
same problems: messy imports, missing metadata, duplicate records, inconsistent
genres, stale artwork, fragile local services, and unclear security boundaries.

The repository is public open-source software at
[`cmsjade5000/Vault966R2`](https://github.com/cmsjade5000/Vault966R2), maintained
from the `public-main` default branch. The private runtime database, logs, local
backups, and environment files are intentionally excluded from source control.

## Program Fit

Vault 966 fits the program best as a maintainer-automation project, not as a
generic AI demo. The repository already has durable agent instructions,
task-specific Codex skills, verification wrappers, CI checks, generated API
clients, and security/privacy review rules. API credits would help convert that
structure into repeatable OSS workflows contributors can run, review, and
improve.

The strongest application narrative is:

> Vault 966 is a self-hosted FastAPI movie-library and recommendation system
> with Codex-native maintainer workflows for import validation, metadata
> cleanup, duplicate resolution, artwork audits, release notes, security checks,
> and test orchestration. Codex access and API credits would help turn these
> workflows into repeatable OSS maintenance automation, improving PR review,
> data quality, and security coverage while preserving strict private-data
> boundaries.

## Existing Codex Surface

Vault 966 already has a Codex-native maintenance surface:

- `AGENTS.md` defines project boundaries, review standards, verification
  commands, and live-service rules.
- `docs/codex-runbook.md` gives coding agents a repeatable handoff for setup,
  skills, verification, and live deployment checks.
- `skills/` contains task-specific workflows for imports, metadata cleanup,
  duplicate resolution, artwork audits, database health, test execution,
  security review, and release notes.
- `make codex.check`, `make codex.full`, and `make codex.live` provide stable
  verification commands for local and agent-assisted work.
- `data/samples/` and `docs/demo-data.md` provide synthetic import cases for
  public demos and issue reproduction without exposing private collection data.

Codex credits and access would be used for maintainer tasks that are expensive
to do manually but straightforward to supervise:

- Review pull requests for authentication, input validation, PII exposure,
  unsafe rendering, and route authorization gaps.
- Validate imported movie data and produce reviewable cleanup patches.
- Triage metadata, artwork, duplicate, and database-health issues.
- Generate release notes from merged changes.
- Run and summarize tests, lint checks, OpenAPI drift checks, and security scans.
- Keep documentation, API clients, and operational runbooks aligned with code.

## API Credit Use

API credits would support automation in four practical areas:

- **Maintainer review loops**: summarize PR diffs, identify risky files, and
  produce focused review checklists.
- **Data-quality workflows**: enrich and validate movie metadata against
  deterministic lookup utilities while keeping private database contents local.
- **Release and security workflows**: draft release notes, triage static-analysis
  results, and suggest small remediation patches.
- **Semantic search experimentation**: test OpenAI-compatible embedding flows for
  self-hosted search while keeping API keys server-side and cache behavior
  explicit.

The intended model is supervised automation: Codex proposes or applies narrow
changes, maintainers review them, and destructive database work requires explicit
approval.

## Current Evidence

Vault 966 already has selection-relevant maintainer infrastructure:

- CI runs Python formatting, Ruff, Prettier, JavaScript tests, pytest,
  OpenAPI/client drift checks, and an optional Docker build.
- `scripts/codex_check.sh` provides stable `quick`, `full`, `live`, `status`, and
  `skills` verification modes.
- Generated OpenAPI, Python client, and TypeScript definitions make API drift
  visible.
- `AGENTS.md` documents route auth, input validation, SQL safety, HTML/JS
  rendering, PII logging, security headers, and open-redirect expectations.
- GitHub issue templates, pull request templates, CODEOWNERS, and Dependabot are
  present so contributors and automation have clear entry points.
- Project-specific skills cover recurring maintainer work instead of relying on
  one-off prompt memory.

## Public Repository Hygiene

Keep tracked data and generated report artifacts suitable for public review.
Synthetic samples and documentation belong in the repository; private collection
snapshots, local audit outputs, and movie-record exports should stay out of the
public source tree if they expose personal collection details or distract from
the reusable software.

## Public Readiness Checklist

- [x] Choose and commit a license.
- [x] Make the GitHub repository public after private-data review.
- [x] Add repository description and topics.
- [x] Confirm GitHub private vulnerability reporting in the repository security
      settings after the repository is public.
- [x] Review tracked `data/` and `reports/` artifacts for public suitability.
- [x] Add initial `good first issue` and `help wanted` issues.
- [x] Set `public-main` as the default branch.
- [ ] Keep `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `AGENTS.md`
      aligned as the maintainer workflow evolves.
- [x] Publish a short roadmap of contributor-friendly tasks.
- [x] Add synthetic demo import data for public examples and screenshots.

## README Summary

Vault 966 is a self-hosted movie-library and recommendation system with a
FastAPI backend, server-rendered UI, SQLite/Postgres support, generated API
clients, semantic search, and Codex-ready maintainer workflows. The project uses
Codex for import review, metadata cleanup, duplicate resolution, artwork audits,
security checks, test orchestration, release notes, and live-service
verification.
