# Repo-Scoped Codex Skills

Codex discovers repository skills from `.agents/skills` while walking from the
current working directory to the repository root.

The skill directories here are symlinks to `../../skills/*` so the existing
project map remains stable and Codex still sees these workflows automatically.
Keep the canonical skill content in `skills/<name>/SKILL.md`.
