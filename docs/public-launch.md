# Public Launch Runbook

Use this before changing the GitHub repository from private to public.

## Recommended Launch Path

For the cleanest public first impression, publish from a clean public branch or
fresh public repository rather than exposing old private development history.
The current working tree is being prepared for public use, but older commits may
still contain private-looking import snapshots, generated reports, messy WIP
history, or implementation details that are not useful to contributors.

Recommended sequence:

1. Finish and review the public-readiness changes.
2. Confirm tracked files only include source, docs, synthetic samples, and safe
   metadata.
3. Run a secret scan against the clean tree and, separately, any history that
   will be published.
4. Create a clean public branch or fresh public repository with a curated initial
   commit.
5. Confirm GitHub private vulnerability reporting in repository security
   settings.
6. Require CI for pull requests once branch protection is available.
7. Publish starter issues and labels before sharing the application link.

## Files That Should Stay Private

Do not publish:

- `.env` files or real environment values.
- SQLite databases, journals, WAL files, or backups.
- Service logs or request logs.
- Private movie exports, import snapshots, staged CSVs, and generated review
  reports.
- Generated collection reports that reveal personal catalog details.

## Public-Safe Examples

Use `data/samples/` and [demo-data.md](demo-data.md) for public examples,
screenshots, issue reproduction, and contributor onboarding.

## GitHub Settings To Confirm

- Repository visibility is public only after history review.
- Description and topics are set.
- Issues are enabled.
- Private vulnerability reporting is enabled.
- Dependabot is enabled for GitHub Actions, npm, and pip.
- Branch protection requires CI on the default branch.
