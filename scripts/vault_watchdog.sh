#!/usr/bin/env bash
set -euo pipefail

LABEL="${LABEL:-com.vault966.server}"
DOMAIN="${DOMAIN:-gui/$(id -u)}"
SERVICE_TARGET="$DOMAIN/$LABEL"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-3}"
HEALTH_RETRY_DELAY="${HEALTH_RETRY_DELAY:-5}"

for ((attempt = 1; attempt <= HEALTH_ATTEMPTS; attempt++)); do
  if curl --fail --silent --show-error --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    exit 0
  fi

  if (( attempt < HEALTH_ATTEMPTS )); then
    sleep "$HEALTH_RETRY_DELAY"
  fi
done

echo "Vault watchdog: health unavailable after ${HEALTH_ATTEMPTS} attempts; restarting $SERVICE_TARGET." >&2
launchctl kickstart -k "$SERVICE_TARGET"
