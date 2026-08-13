#!/usr/bin/env python3
"""Fail closed unless every configured forwarding proxy is an exact IP address."""

from __future__ import annotations

import ipaddress
import os
import sys


def validate(value: str) -> None:
    if not value:
        return

    values = value.split(",")
    if any(not item or item != item.strip() for item in values):
        raise ValueError("must be a comma-separated list of exact IP addresses")

    for value in values:
        ipaddress.ip_address(value)


def main() -> int:
    try:
        validate(os.environ.get("VAULT_TRUSTED_PROXY_IPS", ""))
    except ValueError as exc:
        print(
            "VAULT_TRUSTED_PROXY_IPS is invalid: "
            f"{exc}. Leave it unset for direct connections, or use exact proxy IP addresses; '*' and CIDRs are not allowed.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
