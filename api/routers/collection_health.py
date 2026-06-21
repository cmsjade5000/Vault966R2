from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_admin_or_profile_admin
from api.services.movies_curated import get_collection_recommendation
from api.services.vault_update import load_status, run_update_tasks, start_update


router = APIRouter(prefix="/api/collection-health", tags=["collection-health"])


@router.post("/recommendation/refresh")
def refresh_recommendation(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_profile_admin),
) -> dict:
    recommendation = get_collection_recommendation(db, force=True)
    return {"recommendation": recommendation}


@router.get("/update/status")
def update_status() -> dict:
    return load_status()


@router.post("/update/run")
def update_run(
    background_tasks: BackgroundTasks,
    _: None = Depends(require_admin_or_profile_admin),
) -> dict:
    started, status = start_update()
    if started:
        background_tasks.add_task(run_update_tasks)
    return {"started": started, "status": status}
