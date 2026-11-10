"""Transactional, reversible profile archival. No credential or preference deletion.

Maintenance-only service: no public HTTP reset endpoint. Live execution needs a
separate approved maintenance window and backup; tests use isolated databases.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from api.models.profile import AppSetup, Profile, ProfileArchiveBatch, SetupGrant


def _archive(profile: Profile, batch_id: str, now: datetime) -> None:
    profile.archived_name = profile.name
    profile.name = f"Archived profile {profile.id} ({batch_id[:8]})"
    profile.archived_at = now
    profile.archived_batch_id = batch_id
    profile.session_revision = (profile.session_revision or 0) + 1


def prepare_personal_fresh_start(db: Session, *, expected_active_ids: set[int]) -> str:
    profiles = db.query(Profile).filter(Profile.archived_at.is_(None)).all()
    record = db.get(AppSetup, 1)
    if not profiles or {profile.id for profile in profiles} != expected_active_ids:
        raise ValueError("Active profiles changed; fresh-start preparation stopped")
    if record is not None and record.personal_sign_in_only and not record.completed:
        raise ValueError("Fresh setup is already pending")
    now = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())
    batch = ProfileArchiveBatch(
        id=batch_id,
        previous_setup_completed=bool(record and record.completed),
        previous_completed_at=record.completed_at if record else None,
        previous_owner_profile_id=record.owner_profile_id if record else None,
        previous_personal_sign_in_only=bool(record and record.personal_sign_in_only),
        previous_local_setup_only=bool(record and record.local_setup_only),
        created_at=now,
    )
    try:
        db.query(SetupGrant).filter(SetupGrant.consumed_at.is_(None)).update(
            {SetupGrant.consumed_at: int(now.timestamp())}
        )
        db.add(batch)
        for profile in profiles:
            _archive(profile, batch_id, now)
        if record is None:
            record = AppSetup(id=1)
            db.add(record)
        record.unlock_revision = (record.unlock_revision or 0) + 1
        record.completed = False
        record.completed_at = None
        record.owner_profile_id = None
        record.personal_sign_in_only = True
        record.local_setup_only = True
        record.updated_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise
    return batch_id


def restore_profile_archive(
    db: Session, *, batch_id: str, expected_active_ids: set[int]
) -> str | None:
    """Restore the previous accounts; archive replacement accounts, retain all data.

    Old sessions never return: each archived/restored profile's revision advances.
    Must run on archive-aware code, never by pointing old code at this database.
    """
    batch = db.get(ProfileArchiveBatch, batch_id)
    active = db.query(Profile).filter(Profile.archived_at.is_(None)).all()
    archived = (
        db.query(Profile)
        .filter(Profile.archived_batch_id == batch_id, Profile.archived_at.isnot(None))
        .all()
    )
    if batch is None or batch.restored_at is not None or not archived:
        raise ValueError("Archive is unavailable or already restored")
    if {profile.id for profile in active} != expected_active_ids:
        raise ValueError("Active profiles changed; archive restoration stopped")
    now = datetime.now(timezone.utc)
    replacement_batch_id = str(uuid.uuid4()) if active else None
    record = db.get(AppSetup, 1)
    if record is None:
        raise ValueError("Setup record is unavailable")
    try:
        db.query(SetupGrant).filter(SetupGrant.consumed_at.is_(None)).update(
            {SetupGrant.consumed_at: int(now.timestamp())}
        )
        if replacement_batch_id:
            db.add(
                ProfileArchiveBatch(
                    id=replacement_batch_id,
                    previous_setup_completed=record.completed,
                    previous_completed_at=record.completed_at,
                    previous_owner_profile_id=record.owner_profile_id,
                    previous_personal_sign_in_only=record.personal_sign_in_only,
                    previous_local_setup_only=record.local_setup_only,
                    created_at=now,
                )
            )
        for profile in active:
            _archive(profile, replacement_batch_id, now)
        db.flush()  # Release active names before restoring their original names.
        for profile in archived:
            profile.name = profile.archived_name
            profile.archived_name = None
            profile.archived_at = None
            profile.archived_batch_id = None
            profile.session_revision = (profile.session_revision or 0) + 1
        record = db.get(AppSetup, 1)
        record.unlock_revision = (record.unlock_revision or 0) + 1
        record.completed = batch.previous_setup_completed
        record.completed_at = batch.previous_completed_at
        record.updated_at = now
        record.owner_profile_id = batch.previous_owner_profile_id
        record.personal_sign_in_only = batch.previous_personal_sign_in_only
        record.local_setup_only = batch.previous_local_setup_only
        batch.restored_at = now
        db.commit()
    except Exception:
        db.rollback()
        raise

    return replacement_batch_id
