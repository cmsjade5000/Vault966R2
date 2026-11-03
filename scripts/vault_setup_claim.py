#!/usr/bin/env python3
"""Human-operated local setup authorization. No secret command-line arguments.

Run personally in an interactive Terminal after separately approved migration and
archival. Never invoke this command through agent tools for a real installation.
"""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        parser.error("Run this command yourself in an interactive local Terminal.")
    database = args.database
    if database.is_symlink() or not database.is_file():
        parser.error("An existing regular private database is required.")
    metadata = database.stat()
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        parser.error("Database must be owned by this user with private permissions.")
    name = input("Owner name (used to sign in): ").strip()
    print(
        "Choose a fresh one-time setup code of 20–128 characters. Use your password manager; do not reuse your Vault password.",
        file=sys.stderr,
    )
    code = getpass.getpass("One-time setup code (hidden): ")
    confirm = getpass.getpass("Confirm one-time setup code (hidden): ")
    if code != confirm:
        print("Codes did not match; no grant issued.", file=sys.stderr)
        return 1
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session
    from api.services.setup_grants import SetupGrantError, issue_setup_grant

    engine = create_engine(URL.create("sqlite", database=str(database.resolve())), echo=False)
    try:
        with Session(engine) as db:
            issue_setup_grant(db, owner_name=name, code=code)
    except SetupGrantError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
        code = confirm = ""
    print(
        "Private setup claim ready for 10 minutes. Personally open http://127.0.0.1:8000/setup/claim and enter your one-time code there. It binds once to that browser. Then enter and submit your new Vault password yourself."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
