---
name: test-suite-runner
description: Execute the full test suite (pytest for backend, npm test for frontend) and summarize pass/fail status plus warnings. Use when asked to run tests, report failures, or provide a concise test summary.
---

# Test Suite Runner

## Goal
Run backend and frontend test suites, then return a compact report with failures and warnings.

## Workflow
1. Run backend tests: `pytest`.
2. Run frontend tests: `npm test` (or the repo-defined test script).
3. Capture warnings (pytest warnings summary, npm stderr).
4. Summarize results and point to failing tests or missing scripts.

## Reporting format
- `pytest`: pass/fail + number of tests + warnings.
- `npm test`: pass/fail; if script missing, report and suggest `npm run` to list scripts.
- If either fails, include the first failure block and propose next steps.

## Notes
- Do not dump full logs unless requested; keep output concise.
- If frontend tests are not configured, report that explicitly.
