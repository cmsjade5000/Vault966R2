#!/usr/bin/env bash

# Source this file in your shell for a few handy dev helpers.
alias api="LOG_STYLE=console uvicorn api.main:app --reload --no-proxy-headers"
alias apijson="uvicorn api.main:app --reload --no-proxy-headers | jq"
alias apilogs='docker compose logs -f api | jq'
alias apistatus='curl -s http://127.0.0.1:8000/health | jq'
