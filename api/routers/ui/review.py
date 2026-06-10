from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role, require_same_origin
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.models.source_sync import SourceFieldDecision
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
    defer_source_row_for_research,
    dismiss_duplicate,
    get_source_review_queue,
    latest_active_snapshot,
    partition_source_review_queue,
    undo_source_field_decision,
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
REVIEW_VIEWS = {
    "differences",
    "research",
    "ambiguous",
    "new",
    "duplicates",
    "vault",
}


@router.get("/ui/review", response_class=HTMLResponse)
def review_queue_ui(
    request: Request,
    view: str | None = None,
    row: int | None = Query(default=None, ge=1),
    movie: int | None = Query(default=None, ge=1),
    undo_decision: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
):
    requested_view = view
    view = view or "differences"
    if view not in REVIEW_VIEWS:
        raise HTTPException(status_code=404, detail="Review category not found")
    queue, finding_count = get_review_queue(db)
    source_groups = partition_source_review_queue(get_source_review_queue(db))
    review_counts = {
        **{name: len(items) for name, items in source_groups.items()},
        "vault": len(queue),
    }
    review_tabs = [
        ("differences", "Differences"),
        ("research", "Needs research"),
        ("ambiguous", "Ambiguous"),
        ("new", "New movies"),
        ("duplicates", "Duplicates"),
        ("vault", "Vault checks"),
    ]
    if requested_view is None and review_counts[view] == 0:
        view = next(
            (key for key, _ in review_tabs if review_counts[key]),
            view,
        )
    review_view_label = dict(review_tabs)[view]
    selected_queue = queue if view == "vault" else source_groups[view]
    selected_index = 0
    requested_item_id = movie if view == "vault" else row
    if requested_item_id is not None:
        selected_index = next(
            (
                index
                for index, item in enumerate(selected_queue)
                if (
                    item.movie.id
                    if view == "vault"
                    else item.source_row.id
                )
                == requested_item_id
            ),
            0,
        )
    review_item = selected_queue[selected_index] if selected_queue else None
    item_param = "movie" if view == "vault" else "row"
    previous_item = selected_queue[selected_index - 1] if selected_index > 0 else None
    next_item = (
        selected_queue[selected_index + 1]
        if selected_index + 1 < len(selected_queue)
        else None
    )

    def item_url(item) -> str | None:
        if item is None:
            return None
        item_id = item.movie.id if view == "vault" else item.source_row.id
        return f"/ui/review?view={quote(view)}&{item_param}={item_id}"

    next_nonempty_view = next(
        (
            (key, label)
            for key, label in review_tabs
            if key != view and review_counts[key]
        ),
        None,
    )
    source_snapshot = latest_active_snapshot(db)
    undo_record = db.get(SourceFieldDecision, undo_decision) if undo_decision else None
    if undo_record is not None and undo_record.undone_at is not None:
        undo_record = None
    response = TEMPLATES.TemplateResponse(
        request,
        "review_queue.html",
        {
            "queue": queue,
            "source_queue": selected_queue if view != "vault" else [],
            "source_groups": source_groups,
            "source_snapshot": source_snapshot,
            "finding_count": finding_count,
            "review_counts": review_counts,
            "review_tabs": review_tabs,
            "total_review_count": len(
                {
                    item.source_row.id
                    for items in source_groups.values()
                    for item in items
                }
            )
            + len(queue),
            "review_view": view,
            "review_view_label": review_view_label,
            "review_item": review_item,
            "review_position": selected_index + 1 if review_item else 0,
            "review_queue_count": len(selected_queue),
            "previous_item_url": item_url(previous_item),
            "next_item_url": item_url(next_item),
            "next_nonempty_view": next_nonempty_view,
            "undo_record": undo_record,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


def _source_action_redirect(
    message: str,
    *,
    view: str = "differences",
    undo_decision: int | None = None,
) -> RedirectResponse:
    if view not in REVIEW_VIEWS:
        view = "differences"
    params = [f"view={quote(view)}", f"message={quote(message)}"]
    if undo_decision is not None:
        params.append(f"undo_decision={undo_decision}")
    return RedirectResponse(url=f"/ui/review?{'&'.join(params)}", status_code=303)


@router.post("/ui/review/source-row/{row_id}/field/{field_name}/{decision}")
def decide_source_review_field(
    row_id: int,
    field_name: str,
    decision: str,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
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
        f"{labels[decision]} for {result.movie.vault_id or result.movie.title}.",
        view=view,
        undo_decision=result.id,
    )


@router.post("/ui/review/source-row/{row_id}/defer")
def defer_source_review_movie(
    row_id: int,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        records = defer_source_row_for_research(
            db,
            row_id=row_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    movie = records[0].movie
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} moved to Needs Research. Showing the next movie.",
        view=view,
    )


@router.post("/ui/review/source-decision/{decision_id}/undo")
def undo_source_review_field(
    decision_id: int,
    request: Request,
    view: str = "differences",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        result = undo_source_field_decision(
            db,
            decision_id=decision_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(
        f"Decision undone for {result.movie.vault_id or result.movie.title}.",
        view=view,
    )


@router.post("/ui/review/source-row/{row_id}/match/{movie_id}")
def confirm_source_row_match(
    row_id: int,
    movie_id: int,
    request: Request,
    view: str = "ambiguous",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
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
    return _source_action_redirect(
        "Source row matched to the selected Vault entry.",
        view=view,
    )


@router.post("/ui/review/source-row/{row_id}/create")
def create_source_row_movie(
    row_id: int,
    request: Request,
    view: str = "new",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        movie = create_movie_from_source_row(
            db,
            row_id=row_id,
            profile_id=get_active_profile_id(request, db),
        )
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect(f"{movie.vault_id} added to the Vault.", view=view)


@router.post("/ui/review/source-row/{row_id}/dismiss-duplicate")
def dismiss_source_duplicate(
    row_id: int,
    view: str = "duplicates",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> RedirectResponse:
    try:
        dismiss_duplicate(db, row_id=row_id)
    except SourceSyncError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_action_redirect("Duplicate source row dismissed.", view=view)


def _load_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@router.post("/ui/review/{movie_id}/checked")
def mark_review_checked(
    movie_id: int,
    request: Request,
    view: str = "vault",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
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
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} marked as checked.",
        view=view,
    )


@router.post("/ui/review/{movie_id}/needs-fix")
def mark_review_needs_fix(
    movie_id: int,
    request: Request,
    view: str = "vault",
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
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
    return _source_action_redirect(
        f"{movie.vault_id or movie.title} added to Flags.",
        view=view,
    )
