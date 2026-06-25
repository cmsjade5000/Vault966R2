---
name: release-notes-generator
description: Draft release notes from a time range or list of changes, summarizing new movies added, significant code changes, and bug fixes. Use when asked to generate release notes or summaries.
---

# Release Notes Generator

## Goal
Create concise release notes grouped by movies added, code changes, and fixes.

## Inputs
- Time range (e.g., last 7 days, git commit range).
- Explicit list of changes (commits, PRs, or bullet list).

## Workflow
1. Collect changes within the specified range or list.
2. Categorize into:
   - New movies added
   - Significant code changes
   - Bug fixes
3. Write short, user-facing bullets.
4. Highlight breaking changes if present.

## Formatting
- Start with a short headline and date range.
- Use three sections with bullet points.
- Keep bullets short and action-focused.

## Example
**Release notes (Dec 10–Dec 17)**
- **New movies**
  - Added 24 titles including _Blade Runner 2049_ and _Arrival_.
- **Code changes**
  - Added genre filtering on the library search.
- **Fixes**
  - Fixed flagged movie updates failing with empty runtimes.
