---
name: draft-conventional-commit
description: Draft a Conventional Commits message from a short change summary. Use when a user asks for a conventional commit message, commit subject, or type/scope selection based on changes.
---

# Draft Conventional Commit Messages

## Output
- Emit a single Conventional Commits subject line by default: `type(scope): subject`.
- Include body/footer only if the user asks or the summary indicates a breaking change.

## Steps
1. Read the summary and identify the primary change category.
2. Choose the most specific Conventional Commits type.
3. Infer a short scope from the area touched (optional).
4. Write a concise, imperative subject (<=72 chars) with no trailing period.
5. If breaking change is explicit, add `!` and a `BREAKING CHANGE:` footer.

## Type selection heuristics
- `feat`: new user-visible capability or API.
- `fix`: bug or regression fix.
- `refactor`: internal change with no behavior change.
- `perf`: performance improvement.
- `docs`: documentation-only.
- `test`: tests-only.
- `chore`: maintenance, tooling, deps, cleanup.
- `build`: build system or dependencies.
- `ci`: CI config.
- `revert`: explicit revert.
- `style`: formatting, linting, whitespace.

If multiple changes are present, choose the dominant one; ask a brief clarification only if the type is ambiguous.

## Scope guidance
- Use a short noun from the summary (e.g., `ui`, `api`, `auth`, `db`, `tests`, `deps`).
- Omit scope if none is clear.

## Examples
- Summary: "Add genre filters to movie search UI" -> `feat(ui): add genre filters to movie search`
- Summary: "Fix flagged movie update when runtime empty" -> `fix(movies): handle empty runtime on update`
- Summary: "Format JS files with Prettier" -> `style(js): format files with prettier`
