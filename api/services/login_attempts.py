from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import Request

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 60

_login_attempt_lock = Lock()
_login_attempts: dict[str, deque[float]] = defaultdict(deque)


def _client_key(request: Request) -> str:
    """Use the direct peer only; forwarded headers are not trusted here."""
    return request.client.host if request.client else "unknown"


def reserve_login_attempt(request: Request) -> bool:
    """Reserve a bounded credential-verification slot for the direct client."""
    now = monotonic()
    cutoff = now - LOGIN_ATTEMPT_WINDOW_SECONDS
    key = _client_key(request)
    with _login_attempt_lock:
        attempts = _login_attempts[key]
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= MAX_FAILED_LOGIN_ATTEMPTS:
            return False
        attempts.append(now)
        return True


def clear_login_attempts(request: Request) -> None:
    """A successful credential check restores the client's normal login flow."""
    key = _client_key(request)
    with _login_attempt_lock:
        _login_attempts.pop(key, None)


def clear_login_attempts_for_tests() -> None:
    with _login_attempt_lock:
        _login_attempts.clear()
