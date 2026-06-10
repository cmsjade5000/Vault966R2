from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.movie_review import (
    detect_review_issues,
    get_review_queue,
    record_review_decision,
)
from api.services.source_sync import (
    SourceSyncError,
    assign_source_row_match,
    create_movie_from_source_row,
    decide_source_field,
    dismiss_duplicate,
    get_source_review_queue,
    latest_active_snapshot,
)
from api.services.profiles import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    ensure_profile_cookie,
    get_active_profile_id,
    get_profiles,
)
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])


@router.get("/ui/review", response_class=HTMLResponse)
def review_queue_ui(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
):
    queue, finding_count = get_review_queue(db)
    source_queue = get_source_review_queue(db)
    source_snapshot = latest_active_snapshot(db)
    response = TEMPLATES.TemplateResponse(
        request,
        "review_queue.html",
        {
            "queue": queue,
            "source_queue": source_queue,
            "source_snapshot": source_snapshot,
            "finding_count": finding_count,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


def _source_action_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/ui/review?message={quote(message)}", status_code=303)


@router.post("/ui/review/source-row/{row_id}/field/{field_name}/{decision}")
def decide_source_review_field(
    row_id: int,
    field_name: str,
    decision: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    try:
        result = decide_source_field(
            db,
            row_id=row_id,
            field_name=field_name,
            decision=decision,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    labels = {
        "use_source": "Source value applied",
        "keep_vault": "Vault value kept",
        "needs_research": "Sent to verification",
    }
    return _source_action_redirect(
        f"{labels[decision]} for {result.movie.vault_id or result.movie.title}."
    )


@router.post("/ui/review/source-row/{row_id}/match/{movie_id}")
def confirm_source_row_match(
    row_id: int,
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    try:
        assign_source_row_match(
            db,
            row_id=row_id,
            movie_id=movie_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect("Source row matched to the selected Vault entry.")


@router.post("/ui/review/source-row/{row_id}/create")
def create_source_row_movie(
    row_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    try:
        movie = create_movie_from_source_row(
            db,
            row_id=row_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(f"{movie.vault_id} added to the Vault.")


@router.post("/ui/review/source-row/{row_id}/dismiss-duplicate")
def dismiss_source_duplicate(
    row_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    try:
        dismiss_duplicate(db, row_id=row_id)
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect("Duplicate source row dismissed.")


def _load_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.post("/ui/review/{movie_id}/checked")
def mark_review_checked(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    movie = _load_movie(db, movie_id)
    issues = detect_review_issues(movie)
    record_review_decision(
        db,
        movie=movie,
        issues=issues,
        decision="looks_right",
        profile_id=get_active_profile_id(request, db),
    )
    message = quote(f"{movie.vault_id or movie.title} marked as checked.")
    return RedirectResponse(url=f"/ui/review?message={message}", status_code=303)


@router.post("/ui/review/{movie_id}/needs-fix")
def mark_review_needs_fix(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
) -> RedirectResponse:
    movie = _load_movie(db, movie_id)
    issues = detect_review_issues(movie)
    if movie.flag is None:
        db.add(
            MovieFlag(
                movie_id=movie.id,
                reason="Human review",
                notes="; ".join(issue.label for issue in issues),
            )
        )
        db.flush()
    record_review_decision(
        db,
        movie=movie,
        issues=issues,
        decision="needs_fix",
        profile_id=get_active_profile_id(request, db),
    )
    message = quote(f"{movie.vault_id or movie.title} added to Flags.")
    return RedirectResponse(url=f"/ui/review?message={message}", status_code=303)
