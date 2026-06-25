---
name: poster-backdrop-audit
description: Audit movies for missing or low-quality posters/backdrops, fetch replacements from TMDb, and propose updates. Use when asked to improve artwork coverage or quality.
---

# Poster & Backdrop Audit

## Goal
Identify missing or low-quality artwork and propose replacements.

## Workflow
1. Query movies with missing `poster_url` or `backdrop_url`.
2. Optionally detect low-quality images (very small sizes).
3. Fetch artwork from TMDb for each candidate.
4. Propose updates and apply with confirmation.

## Source
- Use TMDb image endpoints via `api/services/movie_lookup.py`.
- Prefer higher-res poster/backdrop sizes.

## Output
- List of affected movies with current URLs.
- Suggested new poster/backdrop URLs.
- `PATCH /movies/{id}` payloads.

## Notes
- Avoid overwriting custom/curated art without user confirmation.
- Skip if TMDb ID is missing; report as follow-up.
