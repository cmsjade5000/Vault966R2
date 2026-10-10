"""Private, expiring setup grants issued by a human-operated local command.

Codes are accepted once, then bound to one HttpOnly browser nonce. The owner
transaction consumes that binding atomically. Never log codes, nonces or hashes.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from api.models.profile import AppSetup, SetupGrant
from api.services.credentials import _hash_secret, new_secret_hash

SETUP_BROWSER_COOKIE = "vault_setup_browser"
SETUP_COOKIE_PATH = "/setup"
GRANT_TTL_SECONDS = 10 * 60
CODE_MIN_LENGTH = 20
CODE_MAX_LENGTH = 128
NONCE_RE = re.compile(r"[A-Za-z0-9_-]{43}")


class SetupGrantError(ValueError):
    pass


def _now(now: int | None) -> int:
    return int(time.time()) if now is None else now


def browser_digest(nonce: str | None) -> str:
    if not isinstance(nonce, str) or not NONCE_RE.fullmatch(nonce):
        raise SetupGrantError("Private setup claim required.")
    return hashlib.sha256(nonce.encode("ascii")).hexdigest()


def issue_setup_grant(db: Session, *, owner_name: str, code: str, now: int | None = None) -> None:
    """Maintenance-only. Real invocation must be initiated by Cory at a local TTY."""
    from api.services.setup import is_setup_complete

    name = owner_name.strip()
    if not name or len(name) > 80 or not CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH:
        raise SetupGrantError("Owner name and a 20–128 character private setup code are required.")
    if is_setup_complete(db):
        raise SetupGrantError("Setup is complete; no grant can be issued.")
    timestamp = _now(now)
    salt, digest = new_secret_hash(code)
    try:
        setup = db.get(AppSetup, 1)
        if setup is None:
            setup = AppSetup(id=1, completed=False)
            db.add(setup)
        setup.personal_sign_in_only = True
        setup.local_setup_only = True
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        elif dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            raise SetupGrantError("Setup grant unavailable for this database.")
        values = dict(
            id=1,
            generation=str(uuid.uuid4()),
            owner_name=name,
            code_salt=salt,
            code_hash=digest,
            issued_at=timestamp,
            expires_at=timestamp + GRANT_TTL_SECONDS,
            browser_hash=None,
            bound_at=None,
            consumed_at=None,
        )
        db.execute(
            insert(SetupGrant)
            .values(**values)
            .on_conflict_do_update(index_elements=["id"], set_=values)
        )
        db.commit()
        db.expire_all()
    except Exception:
        db.rollback()
        raise


def bind_setup_grant(
    db: Session, *, code: str, browser_nonce: str | None, now: int | None = None
) -> None:
    timestamp = _now(now)
    digest = browser_digest(browser_nonce)
    grant = db.get(SetupGrant, 1)
    if (
        not isinstance(code, str)
        or not CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH
        or grant is None
        or grant.issued_at > timestamp
        or grant.expires_at <= timestamp
        or grant.consumed_at is not None
        or grant.browser_hash is not None
    ):
        raise SetupGrantError("Setup code invalid, expired or already claimed.")
    candidate = _hash_secret(code, salt_hex=grant.code_salt)
    if not hmac.compare_digest(candidate, grant.code_hash):
        raise SetupGrantError("Setup code invalid, expired or already claimed.")
    try:
        claimed = db.execute(
            update(SetupGrant)
            .where(
                SetupGrant.id == 1,
                SetupGrant.generation == grant.generation,
                SetupGrant.expires_at > timestamp,
                SetupGrant.browser_hash.is_(None),
                SetupGrant.consumed_at.is_(None),
            )
            .values(browser_hash=digest, bound_at=timestamp)
        )
        if claimed.rowcount != 1:
            raise SetupGrantError("Setup code invalid, expired or already claimed.")
        db.commit()
        db.expire_all()
    except Exception:
        db.rollback()
        raise


def require_bound_setup_grant(
    db: Session, *, browser_nonce: str | None, now: int | None = None
) -> SetupGrant:
    timestamp = _now(now)
    digest = browser_digest(browser_nonce)
    grant = db.get(SetupGrant, 1)
    if (
        grant is None
        or grant.browser_hash is None
        or grant.bound_at is None
        or grant.consumed_at is not None
        or grant.issued_at > timestamp
        or grant.expires_at <= timestamp
        or not hmac.compare_digest(digest, grant.browser_hash)
    ):
        raise SetupGrantError("Private setup claim required.")
    return grant


def consume_setup_grant(db: Session, *, browser_nonce: str | None, now: int | None = None) -> None:
    """No commit: consumption must share the owner/credential creation transaction."""
    timestamp = _now(now)
    grant = require_bound_setup_grant(db, browser_nonce=browser_nonce, now=timestamp)
    claimed = db.execute(
        update(SetupGrant)
        .where(
            SetupGrant.id == 1,
            SetupGrant.generation == grant.generation,
            SetupGrant.expires_at > timestamp,
            SetupGrant.browser_hash == browser_digest(browser_nonce),
            SetupGrant.consumed_at.is_(None),
        )
        .values(consumed_at=timestamp)
    )
    if claimed.rowcount != 1:
        raise SetupGrantError("Private setup claim required.")
