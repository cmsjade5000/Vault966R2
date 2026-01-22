from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_admin
from api.services.movies_curated import get_collection_recommendation


router = APIRouter(prefix="/api/collection-health", tags=["collection-health"])


@router.post("/recommendation/refresh")
def refresh_recommendation(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> dict:
    recommendation = get_collection_recommendation(db, force=True)
    return {"recommendation": recommendation}
