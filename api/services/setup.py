from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from api.config import settings
from api.models.profile import AppSetup, Profile, ProfileCredential
from api.services.credentials import build_profile_credential, credential_matches
from api.services.profiles import ROLE_ADMIN, ROLE_REVIEWER

SETUP_SINGLETON_ID = 1
PROFILE_NAME_MAX_LENGTH = 80
ACCESS_KEY_MAX_LENGTH = 128
PASSCODE_MAX_LENGTH = 128
PASSCODE_MIN_LENGTH = 4


class SetupError(ValueError):
    pass


@dataclass(frozen=True)
class SetupResult:
    profile: Profile


def legacy_credentials_configured() -> bool:
    return bool(
        (settings.login_access_key and settings.login_passcode)
        or (settings.login_access_key_user_a and settings.login_passcode_user_a)
        or (settings.login_access_key_user_b and settings.login_passcode_user_b)
    )


def setup_record(db: Session) -> AppSetup | None:
    return db.get(AppSetup, SETUP_SINGLETON_ID)


def db_credentials_configured(db: Session) -> bool:
    return (
        db.query(ProfileCredential.id).join(Profile).filter(Profile.archived_at.is_(None)).first()
        is not None
    )


def is_setup_complete(db: Session) -> bool:
    record = setup_record(db)
    if record is not None and record.completed:
        return True
    if record is not None and record.personal_sign_in_only:
        return db_credentials_configured(db)
    return legacy_credentials_configured() or db_credentials_configured(db)


def _clean_required(value: str | None, *, field: str, max_length: int) -> str:
    text = (value or "").strip()
    if not text:
        raise SetupError(f"{field} is required.")
    if len(text) > max_length:
        raise SetupError(f"{field} must be {max_length} characters or fewer.")
    return text


def create_first_profile_setup(
    db: Session,
    *,
    profile_name: str | None,
    access_key: str | None,
    passcode: str | None,
    passcode_confirm: str | None,
    bootstrap_browser_nonce: str | None = None,
) -> SetupResult:
    if is_setup_complete(db):
        raise SetupError("Vault 966 setup is already complete.")

    from api.services.setup_grants import (
        SetupGrantError,
        require_bound_setup_grant,
        consume_setup_grant,
    )

    try:
        grant = require_bound_setup_grant(db, browser_nonce=bootstrap_browser_nonce)
    except SetupGrantError as exc:
        raise SetupError("Private setup claim required.") from exc

    clean_name = _clean_required(
        profile_name,
        field="Profile name",
        max_length=PROFILE_NAME_MAX_LENGTH,
    )
    if clean_name != grant.owner_name:
        raise SetupError("Use the owner name chosen for this private setup claim.")
    clean_key = _clean_required(
        access_key or clean_name,
        field="Username",
        max_length=ACCESS_KEY_MAX_LENGTH,
    )
    clean_passcode = _clean_required(
        passcode,
        field="Password",
        max_length=PASSCODE_MAX_LENGTH,
    )
    clean_confirm = (passcode_confirm or "").strip()
    if len(clean_passcode) < PASSCODE_MIN_LENGTH:
        raise SetupError(f"Password must be at least {PASSCODE_MIN_LENGTH} characters.")
    if clean_passcode != clean_confirm:
        raise SetupError("Passwords do not match.")

    now = datetime.now(timezone.utc)
    try:
        consume_setup_grant(db, browser_nonce=bootstrap_browser_nonce)
        # The singleton insert and conditional claim share the credential transaction.
        # A competing setup can never create a second owner after claiming completion.
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        elif dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            raise SetupError("Account setup is unavailable for this database.")
        db.execute(
            insert(AppSetup)
            .values(id=SETUP_SINGLETON_ID, completed=False)
            .on_conflict_do_nothing(index_elements=["id"])
        )
        claimed = db.execute(
            update(AppSetup)
            .where(AppSetup.id == SETUP_SINGLETON_ID, AppSetup.completed.is_(False))
            .values(completed=True, personal_sign_in_only=True, completed_at=now, updated_at=now)
        )
        if claimed.rowcount != 1:
            raise SetupError("Vault 966 setup is already complete.")
        existing = (
            db.query(Profile)
            .filter(Profile.name == clean_name, Profile.archived_at.is_(None))
            .one_or_none()
        )
        if existing is not None:
            profile = existing
            profile.role = ROLE_ADMIN
            profile.session_revision += 1
        else:
            profile = Profile(name=clean_name, role=ROLE_ADMIN)
            db.add(profile)
            db.flush()
        db.query(ProfileCredential).filter(ProfileCredential.profile_id == profile.id).delete()
        db.add(
            build_profile_credential(
                profile_id=profile.id, access_key=clean_key, passcode=clean_passcode
            )
        )
        db.execute(
            update(AppSetup)
            .where(AppSetup.id == SETUP_SINGLETON_ID)
            .values(owner_profile_id=profile.id)
        )
        db.commit()
        db.refresh(profile)
        return SetupResult(profile=profile)
    except SetupGrantError as exc:
        db.rollback()
        raise SetupError("Private setup claim required.") from exc
    except IntegrityError as exc:
        db.rollback()
        raise SetupError("That name is already in use or setup is already complete.") from exc
    except Exception:
        db.rollback()
        raise


def matching_db_credential_profile_id(
    db: Session,
    *,
    access_key: str | None,
    passcode: str | None,
) -> int | None:
    candidate_key = (access_key or "").strip()
    candidate_passcode = (passcode or "").strip()
    if not candidate_key or not candidate_passcode:
        return None
    credentials = (
        db.query(ProfileCredential)
        .join(Profile)
        .filter(Profile.archived_at.is_(None))
        .options(selectinload(ProfileCredential.profile))
        .order_by(ProfileCredential.id.asc())
        .all()
    )
    matches = []
    for credential in credentials:
        if credential_matches(
            credential,
            access_key=candidate_key,
            passcode=candidate_passcode,
        ):
            matches.append(credential.profile_id)
    return matches[0] if len(matches) == 1 else None


def personal_sign_in_only(db: Session) -> bool:
    record = setup_record(db)
    return bool(record and record.personal_sign_in_only)


def create_personal_reviewer(
    db: Session, *, profile_name: str, passcode: str, passcode_confirm: str
) -> Profile:
    from api.services.credentials import access_key_matches

    name = _clean_required(profile_name, field="Name", max_length=PROFILE_NAME_MAX_LENGTH)
    password = _clean_required(passcode, field="Password", max_length=PASSCODE_MAX_LENGTH)
    if len(password) < PASSCODE_MIN_LENGTH:
        raise SetupError(f"Password must be at least {PASSCODE_MIN_LENGTH} characters.")
    if password != (passcode_confirm or "").strip():
        raise SetupError("Passwords do not match.")
    if db.query(Profile.id).filter(Profile.name == name).first():
        raise SetupError("That name is already in use.")
    credentials = (
        db.query(ProfileCredential).join(Profile).filter(Profile.archived_at.is_(None)).all()
    )
    if any(access_key_matches(credential, access_key=name) for credential in credentials):
        raise SetupError("That name is already in use.")
    try:
        profile = Profile(name=name, role=ROLE_REVIEWER)
        db.add(profile)
        db.flush()
        db.add(build_profile_credential(profile_id=profile.id, access_key=name, passcode=password))
        db.commit()
        return profile
    except IntegrityError as exc:
        db.rollback()
        raise SetupError("That name is already in use.") from exc
    except Exception:
        db.rollback()
        raise
