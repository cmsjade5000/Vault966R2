#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-quick}"
shift || true

cd "$ROOT_DIR"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

run_npm_if_present() {
  local script="$1"
  if [[ -f "package.json" ]]; then
    npm run "$script"
  fi
}

show_skills() {
  if [[ -d ".agents/skills" ]]; then
    find .agents/skills -maxdepth 1 -mindepth 1 \( -type l -o -type d \) -print | sort
  else
    echo "Missing .agents/skills"
    return 1
  fi
}

show_duplicate_artifacts() {
  local matches
  matches="$(find . \
    -path './.git' -prune -o \
    -path './.venv' -prune -o \
    -path './node_modules' -prune -o \
    \( -name '* 2.py' -o -name '* 2.js' -o -name '* 2.css' \) \
    -print | sort)"

  if [[ -n "$matches" ]]; then
    echo "$matches"
  else
    echo "None"
  fi
}

case "$MODE" in
  quick)
    "$PYTHON" -m pytest "$@"
    run_npm_if_present lint
    run_npm_if_present test:js
    ;;
  full)
    "$PYTHON" -m black --check .
    "$PYTHON" -m ruff check .
    run_npm_if_present lint
    "$PYTHON" -m pytest "$@"
    run_npm_if_present test:js
    ;;
  live)
    scripts/vault_service.sh restart
    scripts/vault_service.sh verify /health 200 application/json
    scripts/vault_service.sh verify /readyz 200 application/json
    scripts/vault_service.sh verify /login 200 text/html
    echo "Live service verified: /health, /readyz, and /login"
    ;;
  status)
    git status --short
    echo
    echo "Codex skill links:"
    show_skills
    echo
    echo "Finder/editor duplicate artifacts:"
    show_duplicate_artifacts
    echo
    scripts/vault_service.sh status
    ;;
  skills)
    show_skills
    ;;
  *)
    cat >&2 <<USAGE
Usage: scripts/codex_check.sh <quick|full|live|status|skills> [pytest args...]
USAGE
    exit 2
    ;;
esac
