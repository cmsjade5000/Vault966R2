# Documentation Index

Use `docs/` for guidance that should remain useful after a specific task or date.
Dated measurements, screenshots, audits, and generated CSVs belong in `reports/`.

## Product and Architecture

- `feature_matrix.md`: implemented UI capabilities and known gaps
- `legacy-vault-review.md`: migration status and ideas retained from the original Vault
- `nextjs_frontend_plan.md`: historical optional frontend migration plan

## Operations and Integrations

- `siri-shortcut.md`: local Siri Shortcut integration
- `samples.md`: archived CSV preparation workflow

## Active Planning Outside This Folder

- `second-user-permissions-plan.md`: active permissions and profile-role plan
- `design-qa.md`: current Discover implementation QA evidence

Those two files remain at the repository root while their related implementation
work is active. Move completed, durable guidance here in a dedicated cleanup change
after the active branch is committed.

## Maintenance

- Update this index when adding durable documentation.
- Prefer descriptive lowercase filenames with hyphens.
- Put dates in report filenames, not evergreen documentation filenames.
- Do not include credentials, private database contents, or personally identifying logs.
