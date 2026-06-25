from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role, require_same_origin
from api.models.source_sync import SourceSnapshot
from api.services.profiles import (
    ROLE_ADMIN,
    ensure_profile_cookie,
    get_active_profile_id,
    get_profiles,
)
from api.services.source_sync import (
    SourceSyncError,
    apply_first_import_auto_create,
    create_draft_snapshot,
)
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])


def _snapshot_or_404(db: Session, snapshot_id: int) -> SourceSnapshot:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="First import snapshot not found")
    return snapshot


@router.get("/ui/first-import", response_class=HTMLResponse)
def first_import_ui(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    response = TEMPLATES.TemplateResponse(
        request,
        "first_import.html",
        {
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.post("/ui/first-import/upload")
async def upload_first_import_snapshot(
    request: Request,
    source_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    filename = source_file.filename or "collection.csv"
    if len(filename) > 255:
        return RedirectResponse(
            url="/ui/first-import?error=Filename%20is%20too%20long.",
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
        return RedirectResponse(
            url=f"/ui/first-import?error={quote(str(exc))}",
            status_code=303,
        )
    return RedirectResponse(url=f"/ui/first-import/{snapshot.id}/preview", status_code=303)


@router.get("/ui/first-import/{snapshot_id}/preview", response_class=HTMLResponse)
def preview_first_import_snapshot(
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    snapshot = _snapshot_or_404(db, snapshot_id)
    duplicate_rows = sum(1 for row in snapshot.rows if row.duplicate_group)
    response = TEMPLATES.TemplateResponse(
        request,
        "first_import_preview.html",
        {
            "snapshot": snapshot,
            "duplicate_rows": duplicate_rows,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.post("/ui/first-import/{snapshot_id}/auto-create")
def auto_create_first_import_snapshot(
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    _snapshot_or_404(db, snapshot_id)
    try:
        result = apply_first_import_auto_create(
            db,
            snapshot_id=snapshot_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        return RedirectResponse(
            url=f"/ui/first-import/{snapshot_id}/preview?error={quote(str(exc))}",
            status_code=303,
        )
    message = quote(
        f"Created {result.created_count} high-confidence movies. "
        f"{result.review_count + result.duplicate_conflict_count + result.failed_lookup_count} rows remain for review."
    )
    return RedirectResponse(
        url=f"/ui/first-import/{snapshot_id}/preview?message={message}",
        status_code=303,
    )
