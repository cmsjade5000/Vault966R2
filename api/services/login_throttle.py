"""Bounded, per-client protection for failed interactive login attempts.

The key passed to this limiter must come from ``Request.client.host``.  Vault's
launcher makes that the socket peer in direct mode and only enables Uvicorn's
forwarded-header support for an explicitly configured immediate proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable


MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 15 * 60
BLOCK_SECONDS = 15 * 60
MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _AttemptRecord:
    failures: int
    window_started_at: float
    expires_at: float
    blocked_until: float | None = None
    in_flight: int = 0


class LoginAttemptLimiter:
    """Thread-safe, bounded failed-attempt state keyed by a trusted client IP.

    Entries are only removed after their own expiry.  When the capacity is
    exhausted, an unknown key is allowed but not tracked instead of evicting
    another client's record; otherwise an attacker could remove a victim's
    active lockout or create a shared lockout for every new client.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], float] = monotonic,
        max_failed_attempts: int = MAX_FAILED_ATTEMPTS,
        failure_window_seconds: int = FAILURE_WINDOW_SECONDS,
        block_seconds: int = BLOCK_SECONDS,
        max_tracked_clients: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self._clock = clock
        self._max_failed_attempts = max_failed_attempts
        self._failure_window_seconds = failure_window_seconds
        self._block_seconds = block_seconds
        self._max_tracked_clients = max_tracked_clients
        self._records: dict[str, _AttemptRecord] = {}
        self._lock = Lock()

    def begin_attempt(self, client_key: str) -> bool:
        """Atomically reserve one credential attempt for this client.

        A request must call ``record_failure`` or ``clear`` after a successful
        reservation. The in-flight reservation prevents concurrent requests
        from racing past the failed-attempt ceiling.
        """
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            record = self._records.get(client_key)
            if record is None:
                if len(self._records) >= self._max_tracked_clients:
                    # Preserve existing lockouts and availability for a new
                    # client. A network edge limiter handles distributed abuse
                    # when this in-process emergency capacity is exhausted.
                    return True
                record = _AttemptRecord(
                    failures=0,
                    window_started_at=now,
                    expires_at=now + self._failure_window_seconds,
                )
                self._records[client_key] = record
            if record.blocked_until is not None and record.blocked_until > now:
                return False
            if now >= record.expires_at:
                record.failures = 0
                record.window_started_at = now
                record.expires_at = now + self._failure_window_seconds
                record.blocked_until = None
                record.in_flight = 0
            if record.failures + record.in_flight >= self._max_failed_attempts:
                return False
            record.in_flight += 1
            return True

    def record_failure(self, client_key: str) -> None:
        """Complete a reserved attempt as a failed credential check."""
        now = self._clock()
        with self._lock:
            self._purge_expired(now)
            record = self._records.get(client_key)
            if record is None:
                # The key was admitted without tracking because capacity was
                # full. Never replace an existing client's record here.
                return
            record.in_flight = max(0, record.in_flight - 1)
            if now >= record.expires_at:
                record.failures = 1
                record.window_started_at = now
                record.expires_at = now + self._failure_window_seconds
                record.blocked_until = None
                return
            record.failures += 1
            if record.failures >= self._max_failed_attempts:
                record.blocked_until = now + self._block_seconds
                record.expires_at = record.blocked_until

    def cancel_attempt(self, client_key: str) -> None:
        """Release a reservation that could not complete due to an internal error."""
        with self._lock:
            record = self._records.get(client_key)
            if record is None:
                return
            record.in_flight = max(0, record.in_flight - 1)
            if record.failures == 0 and record.in_flight == 0:
                del self._records[client_key]

    def clear(self, client_key: str) -> None:
        """Forget failures after a successful credential or unlock-token check."""
        with self._lock:
            self._records.pop(client_key, None)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [key for key, record in self._records.items() if record.expires_at <= now]
        for key in expired_keys:
            del self._records[key]
