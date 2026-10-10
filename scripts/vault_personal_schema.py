#!/usr/bin/env python3
"""Read-only schema check by default; guarded maintenance bridge only with --apply."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--check-fixed-reservations",
        action="store_true",
        help="Separately authorized bounded application-data aggregate check",
    )
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-schema-sha256")
    parser.add_argument("--allow-live-target", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from api.services.personal_schema_bridge import BridgeError, inspect_database, apply_bridge

    live = Path.home() / "Library/Application Support/Vault966/data/vault.db"
    try:
        if args.apply:
            if not args.expected_version or not args.expected_schema_sha256:
                parser.error(
                    "Apply requires the exact previously checked stamp and schema fingerprint."
                )
            if args.database.resolve() == live.resolve() and not args.allow_live_target:
                parser.error(
                    "Live writes require a separately approved maintenance operation and --allow-live-target."
                )
            result = apply_bridge(
                args.database,
                expected_version=args.expected_version,
                expected_sha=args.expected_schema_sha256,
            )
        else:
            result = inspect_database(
                args.database, verify_fixed_reservations=args.check_fixed_reservations
            )
        print(json.dumps(result, indent=2))  # Metadata only; never credentials or rows.
        return 0
    except BridgeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
