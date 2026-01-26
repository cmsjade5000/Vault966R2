#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

scripts/vault_server.sh start --force

if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:8000/login"
fi
