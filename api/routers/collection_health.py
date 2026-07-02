from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_admin_or_profile_admin
from api.services.movies_curated import get_collection_recommendation
from api.services.vault_update import (
    build_update_preview,
    load_status,
    merge_durable_job_history,
    report_path_for_task,
    request_cancel,
    run_update_tasks,
    start_update,
    task_ids,
)


router = APIRouter(prefix="/api/collection-health", tags=["collection-health"])


@router.post("/recommendation/refresh")
def refresh_recommendation(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_profile_admin),
) -> dict:
    recommendation = get_collection_recommendation(db, force=True)
    return {"recommendation": recommendation}


@router.get("/update/status")
def update_status(db: Session = Depends(get_db)) -> dict:
    return merge_durable_job_history(load_status(), db)


@router.get("/update/preview")
def update_preview(db: Session = Depends(get_db)) -> dict:
    return build_update_preview(db)


@router.get("/update/reports/{task}")
def update_report(task: str) -> FileResponse:
    report_path = report_path_for_task(task)
    if report_path is None:
        raise HTTPException(status_code=404, detail="Unknown maintenance report")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Maintenance report not found")
    return FileResponse(
        report_path,
        media_type="text/csv",
        filename=report_path.name,
    )


@router.post("/update/cancel")
def update_cancel(_: None = Depends(require_admin_or_profile_admin)) -> dict:
    requested, status = request_cancel()
    return {"requested": requested, "status": status}


@router.post("/update/run")
def update_run(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    task: str = "all",
    _: None = Depends(require_admin_or_profile_admin),
) -> dict:
    if task != "all" and task not in task_ids():
        raise HTTPException(status_code=400, detail="Unknown maintenance task")
    profile_id = getattr(request.state, "session_profile_id", None)
    started, status = start_update(
        task,
        db=db,
        started_by_profile_id=profile_id if isinstance(profile_id, int) else None,
        record_job=True,
    )
    if started:
        background_tasks.add_task(run_update_tasks, task, True)
    return {"started": started, "status": status}
