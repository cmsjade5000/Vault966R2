from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role
from api.models.source_sync import SourceSnapshot
from api.services.profiles import (
    ROLE_ADMIN,
    ensure_profile_cookie,
    get_active_profile_id,
    get_profiles,
)
from api.services.source_sync import (
    SourceSyncError,
    create_draft_snapshot,
    reconcile_snapshot,
)
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])


def _snapshot_or_404(db: Session, snapshot_id: int) -> SourceSnapshot:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Source snapshot not found")
    return snapshot


@router.get("/ui/source-sync", response_class=HTMLResponse)
def source_sync_ui(
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    return RedirectResponse(
        url="/ui/movies/health#source-synchronization",
        status_code=302,
    )


@router.post("/ui/source-sync/upload")
async def upload_source_snapshot(
    request: Request,
    source_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> RedirectResponse:
    filename = source_file.filename or "collection.csv"
    if len(filename) > 255:
        return RedirectResponse(
            url="/ui/movies/health?error=Filename%20is%20too%20long." "#source-synchronization",
            status_code=303,
        )
    content = await source_file.read(5 * 1024 * 1024 + 1)
    try:
        snapshot = create_draft_snapshot(
            db,
            filename=filename,
            content=content,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        message = quote(str(exc))
        return RedirectResponse(
            url=f"/ui/movies/health?error={message}#source-synchronization",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/source-sync/{snapshot.id}/preview",
        status_code=303,
    )


@router.get("/ui/source-sync/{snapshot_id}/preview", response_class=HTMLResponse)
def preview_source_snapshot(
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    snapshot = _snapshot_or_404(db, snapshot_id)
    duplicate_rows = sum(1 for row in snapshot.rows if row.duplicate_group)
    response = TEMPLATES.TemplateResponse(
        request,
        "source_sync_preview.html",
        {
            "snapshot": snapshot,
            "duplicate_rows": duplicate_rows,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.post("/ui/source-sync/{snapshot_id}/confirm")
def confirm_source_snapshot(
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> RedirectResponse:
    snapshot = _snapshot_or_404(db, snapshot_id)
    try:
        summary = reconcile_snapshot(db, snapshot)
    except SourceSyncError as exc:
        message = quote(str(exc))
        return RedirectResponse(
            url=f"/ui/source-sync/{snapshot.id}/preview?error={message}",
            status_code=303,
        )
    message = quote(
        f"Snapshot #{snapshot.id} confirmed: {summary['matched']} matched, "
        f"{summary['conflicts']} conflicts."
    )
    return RedirectResponse(url=f"/ui/movies/health?message={message}", status_code=303)
