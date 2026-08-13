from __future__ import annotations

import re
import sys
from collections.abc import Callable

import httpx

REDACTED = "[REDACTED]"

_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"""
    (?P<prefix>
        (?<![A-Za-z0-9_-])
        (?P<key_quote>["']?)
        (?:
            authorization
            | proxy-authorization
            | (?:[a-z0-9]+[_-])?api[_-]?key
            | apikey
            | (?:access|auth)[_-]?token
            | token
            | client[_-]?secret
            | key
        )
        (?P=key_quote)
        \s*[:=]\s*
        (?P<value_quote>["']?)
    )
    (?:(?:bearer|basic)\s+)?
    [^&\s,;#}\])>'"]+
    """,
    re.IGNORECASE | re.VERBOSE,
)


def sanitize_provider_diagnostic(value: object) -> str:
    """Redact provider credentials while retaining useful failure context."""

    return _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}",
        str(value),
    )


def format_provider_error(context: str, error: BaseException) -> str:
    """Format a provider failure without forwarding query or authorization secrets."""

    message = sanitize_provider_diagnostic(error).strip()
    if not message:
        return f"{context}: {type(error).__name__}"
    return f"{context}: {type(error).__name__}: {message}"


def run_provider_cli(main: Callable[[], int]) -> int:
    """Run a provider-backed script with a sanitized terminal failure boundary."""

    try:
        return main()
    except httpx.HTTPError as exc:
        print(format_provider_error("Provider request failed", exc), file=sys.stderr)
        return 1


__all__ = [
    "REDACTED",
    "format_provider_error",
    "run_provider_cli",
    "sanitize_provider_diagnostic",
]
