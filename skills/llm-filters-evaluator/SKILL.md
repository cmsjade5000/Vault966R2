---
name: llm-filters-evaluator
description: Validate and correct LLM-generated movie filters against available facets, report invalid values, and propose safe replacements. Use when LLM filters fail or need auditing.
---

# LLM Filters Evaluator

## Goal
Ensure AI-generated filters match real facets and produce valid queries.

## Workflow
1. Fetch available facets (genres, moods, years).
2. Compare LLM filters to the facet lists.
3. Flag invalid or unknown values.
4. Propose corrected filters or removals.
5. Return a validated filter payload.

## Checks
- Genres/moods not present in the DB.
- Year ranges outside valid bounds.
- Empty or contradictory filters.

## Output
- Invalid values list.
- Suggested replacements (closest match).
- Cleaned filter payload.

## Notes
- Prefer dropping invalid filters over guessing if no clear match.
- Keep corrections minimal and explain any substitutions.
