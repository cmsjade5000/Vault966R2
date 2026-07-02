from __future__ import annotations

import re

from sqlalchemy.orm import Session

from api.models.movie import Movie
from api.models.vault_id import RetiredVaultId

VAULT_ID_RE = re.compile(r"^V(\d+)$", re.IGNORECASE)
LEGACY_RETIRED_VAULT_IDS = (
    "V0087",
    "V0135",
    "V0288",
    "V0309",
    "V0539",
    "V0584",
    "V0631",
    "V0637",
    "V0643",
    "V0695",
    "V0942",
)


def normalize_vault_id(value: object) -> str | None:
    text = str(value or "").strip().upper()
    match = VAULT_ID_RE.fullmatch(text)
    if match is None:
        return None
    return f"V{int(match.group(1)):04d}"


def next_vault_id(db: Session) -> str:
    highest = 0
    used_numbers: set[int] = set()
    for query in (
        db.query(Movie.vault_id).filter(Movie.vault_id.isnot(None)),
        db.query(RetiredVaultId.vault_id),
    ):
        for (value,) in query.all():
            normalized = normalize_vault_id(value)
            if normalized is not None:
                number = int(normalized[1:])
                highest = max(highest, number)
                used_numbers.add(number)

    candidate = highest + 1
    while candidate in used_numbers:
        candidate += 1
    return f"V{candidate:04d}"


def is_vault_id_retired(db: Session, vault_id: object) -> bool:
    normalized = normalize_vault_id(vault_id)
    if normalized is None:
        return False
    return db.get(RetiredVaultId, normalized) is not None


def allocate_vault_id(db: Session, requested: object | None = None) -> str:
    normalized = normalize_vault_id(requested)
    if normalized is None:
        return next_vault_id(db)
    if is_vault_id_retired(db, normalized):
        raise ValueError(f"Vault ID {normalized} is retired and cannot be reused")
    return normalized


def retire_vault_id(
    db: Session,
    vault_id: object,
    *,
    source: str,
    reason: str | None = None,
    deleted_movie_id: int | None = None,
    deleted_movie_title: str | None = None,
) -> RetiredVaultId | None:
    normalized = normalize_vault_id(vault_id)
    if normalized is None:
        return None

    retired = db.get(RetiredVaultId, normalized)
    if retired is None:
        retired = RetiredVaultId(
            vault_id=normalized,
            source=source,
            reason=reason,
            deleted_movie_id=deleted_movie_id,
            deleted_movie_title=deleted_movie_title,
        )
        db.add(retired)
    else:
        if retired.deleted_movie_id is None:
            retired.deleted_movie_id = deleted_movie_id
        if retired.deleted_movie_title is None:
            retired.deleted_movie_title = deleted_movie_title
    return retired


def retire_movie_vault_id(db: Session, movie: Movie, *, source: str, reason: str) -> None:
    retire_vault_id(
        db,
        movie.vault_id,
        source=source,
        reason=reason,
        deleted_movie_id=movie.id,
        deleted_movie_title=movie.title,
    )


def seed_legacy_retired_vault_ids(db: Session) -> None:
    for vault_id in LEGACY_RETIRED_VAULT_IDS:
        retire_vault_id(
            db,
            vault_id,
            source="legacy_gap",
            reason="Known legacy Vault ID gap reserved to prevent reuse.",
        )


def display_vault_id(movie: Movie) -> str:
    return movie.vault_id or f"V{movie.id:04d}"


__all__ = [
    "LEGACY_RETIRED_VAULT_IDS",
    "allocate_vault_id",
    "display_vault_id",
    "is_vault_id_retired",
    "next_vault_id",
    "normalize_vault_id",
    "retire_movie_vault_id",
    "retire_vault_id",
    "seed_legacy_retired_vault_ids",
]
