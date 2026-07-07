from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
    analyze_first_import_snapshot,
    apply_first_import_auto_create,
    create_draft_snapshot,
    first_import_report,
)
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])

SAMPLE_IMPORT_CSV = (
    "Title,Time,Director,Year,Genre,Content Rating,Release Date,HD\n"
    "Arrival,1:56:00,Denis Villeneuve,2016,Science Fiction,PG-13,2016-11-11,HD\n"
    "The Matrix,136,Lana Wachowski and Lilly Wachowski,1999,Science Fiction,R,1999-03-31,HD\n"
)

FIRST_IMPORT_ERROR_MESSAGES = {
    "filename_too_long": "Filename is too long.",
    "missing_columns": (
        "I could not find the required columns. Use Title, Runtime, Director, "
        "and Year headers, or start from the sample CSV."
    ),
    "file_too_large": "That file is over 5 MB. Split it into a smaller CSV or XLSX and try again.",
    "row_limit": (
        "That file has more than 5,000 movie rows. Split the collection and import one file "
        "at a time."
    ),
    "duplicate_snapshot": (
        "That file was already uploaded. Start over with a revised file, or open Vault Health "
        "to continue review."
    ),
    "invalid_runtime": "Invalid runtime. Use minutes, H:MM, or H:MM:SS.",
    "invalid_year": "Invalid year. Use a four-digit release year.",
    "invalid_hd": "Invalid HD value. Use HD, SD, yes, no, true, false, 1, or 0.",
    "worksheet": "Could not read the first worksheet. Save the movie list there or export it as CSV.",
    "source_error": "The import could not be processed. Check the source file and try again.",
}


def _source_error_code(message: str) -> str:
    if "title, runtime, director, and year columns" in message:
        return "missing_columns"
    if "larger than 5 MB" in message:
        return "file_too_large"
    if "more than 5000 rows" in message:
        return "row_limit"
    if "already uploaded" in message:
        return "duplicate_snapshot"
    if "Invalid runtime" in message:
        return "invalid_runtime"
    if "Invalid year" in message or "outside the accepted range" in message:
        return "invalid_year"
    if "Invalid HD value" in message:
        return "invalid_hd"
    if "first worksheet" in message:
        return "worksheet"
    return "source_error"


def _first_import_error_message(request: Request) -> str | None:
    code = request.query_params.get("error")
    if code is None:
        return None
    return FIRST_IMPORT_ERROR_MESSAGES.get(code, FIRST_IMPORT_ERROR_MESSAGES["source_error"])


def _first_import_error_url(code: str) -> str:
    return f"/ui/first-import?error={code}"


def _snapshot_or_404(db: Session, snapshot_id: int) -> SourceSnapshot:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="First import snapshot not found")
    return snapshot


@router.get("/ui/first-import", response_class=HTMLResponse)
@router.get("/ui/onboarding/import", response_class=HTMLResponse)
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
            "is_onboarding": request.url.path == "/ui/onboarding/import",
            "error": _first_import_error_message(request),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.get("/ui/first-import/sample.csv")
@router.get("/ui/onboarding/import/sample.csv")
def first_import_sample_csv(
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> Response:
    return Response(
        content=SAMPLE_IMPORT_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vault966-first-import-sample.csv"'},
    )


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
            url=_first_import_error_url("filename_too_long"),
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
            url=_first_import_error_url(_source_error_code(str(exc))),
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
    import_analysis = analyze_first_import_snapshot(db, snapshot_id=snapshot_id)
    response = TEMPLATES.TemplateResponse(
        request,
        "first_import_preview.html",
        {
            "snapshot": snapshot,
            "duplicate_rows": duplicate_rows,
            "import_analysis": import_analysis,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
            "error": _first_import_error_message(request),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


@router.get("/ui/first-import/{snapshot_id}/report", response_class=HTMLResponse)
def first_import_report_ui(
    snapshot_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    _snapshot_or_404(db, snapshot_id)
    try:
        report = first_import_report(db, snapshot_id=snapshot_id)
    except SourceSyncError as exc:
        return RedirectResponse(
            url=_first_import_error_url(_source_error_code(str(exc))),
            status_code=303,
        )
    response = TEMPLATES.TemplateResponse(
        request,
        "first_import_report.html",
        {
            "report": report,
            "snapshot": report.snapshot,
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
            url=_first_import_error_url(_source_error_code(str(exc))),
            status_code=303,
        )
    return RedirectResponse(
        url=f"/ui/first-import/{result.snapshot_id}/report",
        status_code=303,
    )
