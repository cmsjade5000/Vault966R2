---
name: flag-triage
description: Pull open flags, rank by impact, and propose fixes or routing (metadata cleanup, data correction). Use when asked to triage flags or plan cleanup work.
---

# Flag Triage

## Goal
Prioritize flagged movies and suggest concrete next steps.

## Workflow
1. Fetch open flags (`GET /movies/flags`).
2. Group by reason (e.g., Metadata cleanup, Missing poster).
3. Rank by impact (missing core fields first).
4. Provide suggested fixes or assign to other skills.

## Output
- Ordered list of flagged items with reason and ID.
- Suggested action per item.
- Follow-up skill recommendations (e.g., `metadata-cleanup`).

## Notes
- Avoid resolving flags automatically without confirmation.
