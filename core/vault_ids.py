from __future__ import annotations

import re

from sqlalchemy.orm import Session

from api.models.movie import Movie

VAULT_ID_RE = re.compile(r"^V(\d+)$", re.IGNORECASE)


def normalize_vault_id(value: object) -> str | None:
    text = str(value or "").strip().upper()
    match = VAULT_ID_RE.fullmatch(text)
    if match is None:
        return None
    return f"V{int(match.group(1)):04d}"


def next_vault_id(db: Session) -> str:
    highest = 0
    for (value,) in db.query(Movie.vault_id).filter(Movie.vault_id.isnot(None)).all():
        normalized = normalize_vault_id(value)
        if normalized is not None:
            highest = max(highest, int(normalized[1:]))
    return f"V{highest + 1:04d}"


def display_vault_id(movie: Movie) -> str:
    return movie.vault_id or f"V{movie.id:04d}"


__all__ = ["display_vault_id", "next_vault_id", "normalize_vault_id"]
