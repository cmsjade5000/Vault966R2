from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

SESSION_COOKIE_NAME = "vault_session"
SESSION_VERSION = 1


@dataclass(frozen=True)
class SessionData:
    profile_id: int
    issued_at: int
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_session_token(profile_id: int, *, secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "v": SESSION_VERSION,
        "profile_id": profile_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64encode(payload_raw)
    signature = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature}"


def parse_session_token(token: str, *, secret: str) -> Optional[SessionData]:
    if not token or "." not in token:
        return None
    payload_b64, signature = token.split(".", 1)
    expected = _sign(payload_b64, secret)
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("v") != SESSION_VERSION:
        return None
    try:
        profile_id = int(payload.get("profile_id", 0))
        issued_at = int(payload.get("iat", 0))
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError):
        return None
    if profile_id <= 0:
        return None
    if expires_at <= int(time.time()):
        return None
    return SessionData(profile_id=profile_id, issued_at=issued_at, expires_at=expires_at)
