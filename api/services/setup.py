from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models.profile import AppSetup, Profile, ProfileCredential
from api.services.credentials import build_profile_credential, credential_matches
from api.services.profiles import ROLE_ADMIN

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
    return db.query(ProfileCredential.id).first() is not None


def is_setup_complete(db: Session) -> bool:
    record = setup_record(db)
    if record is not None and record.completed:
        return True
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
) -> SetupResult:
    if is_setup_complete(db):
        raise SetupError("Vault 966 setup is already complete.")

    clean_name = _clean_required(
        profile_name,
        field="Profile name",
        max_length=PROFILE_NAME_MAX_LENGTH,
    )
    clean_key = _clean_required(
        access_key,
        field="Access key",
        max_length=ACCESS_KEY_MAX_LENGTH,
    )
    clean_passcode = _clean_required(
        passcode,
        field="Passcode",
        max_length=PASSCODE_MAX_LENGTH,
    )
    clean_confirm = (passcode_confirm or "").strip()
    if len(clean_passcode) < PASSCODE_MIN_LENGTH:
        raise SetupError(f"Passcode must be at least {PASSCODE_MIN_LENGTH} characters.")
    if clean_passcode != clean_confirm:
        raise SetupError("Passcodes do not match.")

    existing = db.query(Profile).filter(Profile.name == clean_name).one_or_none()
    if existing is not None:
        profile = existing
        profile.role = ROLE_ADMIN
    else:
        profile = Profile(name=clean_name, role=ROLE_ADMIN)
        db.add(profile)
        db.flush()

    if profile.id is None:
        raise SetupError("Could not create the first profile.")

    db.query(ProfileCredential).filter(ProfileCredential.profile_id == profile.id).delete()
    db.add(
        build_profile_credential(
            profile_id=profile.id,
            access_key=clean_key,
            passcode=clean_passcode,
        )
    )

    now = datetime.now(timezone.utc)
    record = setup_record(db)
    if record is None:
        record = AppSetup(id=SETUP_SINGLETON_ID)
        db.add(record)
    record.completed = True
    record.completed_at = now
    record.owner_profile_id = profile.id
    record.updated_at = now
    db.commit()
    db.refresh(profile)
    return SetupResult(profile=profile)


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
        .options(selectinload(ProfileCredential.profile))
        .order_by(ProfileCredential.id.asc())
        .all()
    )
    for credential in credentials:
        if credential_matches(
            credential,
            access_key=candidate_key,
            passcode=candidate_passcode,
        ):
            return credential.profile_id
    return None
