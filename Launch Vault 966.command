#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

scripts/vault_service.sh install

if command -v open >/dev/null 2>&1; then
  for _ in {1..20}; do
    if curl --fail --silent --max-time 1 "http://127.0.0.1:8000/health" >/dev/null; then
      break
    fi
    sleep 1
  done
  open "http://127.0.0.1:8000/login"
fi
