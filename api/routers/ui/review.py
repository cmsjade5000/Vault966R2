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
    response = TEMPLATES.TemplateResponse(
        request,
        "review_queue.html",
        {
            "queue": queue,
            "finding_count": finding_count,
            "profiles": get_profiles(db),
            "active_profile_id": get_active_profile_id(request, db),
        },
    )
    ensure_profile_cookie(request, response, db)
    return response


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
