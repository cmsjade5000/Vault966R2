---
name: duplicate-resolution
description: Identify likely duplicate movie records, propose merges, and generate a safe update plan. Use when asked to dedupe titles, resolve duplicates, or merge records.
---

# Duplicate Resolution

## Goal
Detect likely duplicates and propose a safe, minimal merge plan.

## Workflow
1. Gather candidate duplicates by IDs and title/year.
2. Score similarity (exact IDs > title+year > fuzzy title).
3. Pick the canonical record per pair/group.
4. Produce a merge plan (fields to keep, fields to overwrite).
5. Apply updates and remove duplicates only after confirmation.

## Detection rules
- Exact duplicate: same `imdb_id` or `tmdb_id`.
- Strong match: same normalized title + year.
- Weak match: high title similarity, close year (+/-1).

## Canonical selection
- Prefer records with more complete metadata (runtime, plot, genres, poster).
- Prefer records with verified IDs.

## Output
- Table of duplicate groups with record IDs.
- Proposed canonical ID and field merge notes.
- Update payloads for `PATCH /movies/{id}`.

## Notes
- Never delete records without explicit approval.
- If conflicts exist (runtime/year), present both values and ask.
