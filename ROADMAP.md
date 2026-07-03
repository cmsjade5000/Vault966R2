# Vault 966 Roadmap

This roadmap is intentionally practical: it lists contributor-friendly work that
improves Vault 966 as a self-hosted movie-library system and as a Codex-ready
open-source maintenance project.

## Public OSS Maintenance

- Keep the MIT license, repository description, topics, and starter labels
  current.
- Seed new `good first issue` and `help wanted` issues from this roadmap.
- Maintain `public-main` as the default branch for public contributions.
- Keep `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`, and
  `docs/codex-for-oss.md` aligned as maintainer workflows evolve.

## Contributor-Friendly Tasks

- Expand sample synthetic movie import files that exercise CSV validation without
  exposing private collection data.
- Document a clean local demo path using only synthetic data.
- Expand tests around import review, duplicate detection, and metadata cleanup
  edge cases.
- Improve source-drift and database-health reports so findings are easier to
  turn into issues.
- Add screenshots or short GIFs of the library, review, and Flic workflows using
  non-private sample data.

## Codex Maintainer Automation

- Turn common review checklists into issue or pull request templates.
- Add examples showing when to use each project skill in `skills/`.
- Add a release workflow that drafts notes from merged changes and verification
  results.
- Explore non-destructive Codex-assisted PR review for route authorization,
  template rendering safety, input validation, OpenAPI drift, and logging risks.
- Keep destructive database changes behind explicit maintainer approval.

## Product Direction

- Keep the self-hosted FastAPI/Jinja experience stable and fast on local
  hardware.
- Continue improving Flic recommendations, saved filter presets, and semantic
  search.
- Make metadata, artwork, duplicate, and source-sync review flows easier to
  understand for new maintainers.
- Preserve strict private-data boundaries as the project becomes more reusable.
