---
name: genre-mood-normalizer
description: Audit and standardize genre/mood vocabularies, map aliases, fix casing, and ensure consistent filters. Use when asked to normalize genres/moods, fix filter consistency, or clean taxonomy data.
---

# Genre & Mood Normalizer

## Goal
Normalize genre and mood values to a consistent, deduplicated vocabulary.

## Workflow
1. Export distinct genres and moods from the database.
2. Identify casing variants, aliases, and typos.
3. Propose a canonical mapping table.
4. Apply updates to normalize records.
5. Verify filters and facets still populate correctly.

## Checks
- Case-only duplicates (`sci-fi` vs `Sci-Fi`).
- Alias terms (`Sci Fi`, `Science Fiction` -> `Science Fiction`).
- Typos and stray values (`n/a`, `nan`, empty strings).
- Over-broad values that should be removed (`Other`, `Misc`).

## Output
- Canonical vocabulary list for genres and moods.
- Mapping table of `{old_value -> canonical_value}`.
- Update plan (SQL or API patch).

## Notes
- Avoid deleting values unless they are clearly invalid; map instead.
- Keep a short allowlist for UI filters to prevent noise.
