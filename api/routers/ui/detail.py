from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.services.movies_detail import get_movie_detail
from api.services.ui.spotlight import build_spotlight_reason, get_daily_spotlight_ids
from api.services.ui.templates import TEMPLATES

router = APIRouter()


@router.get("/ui/movies/{movie_id}", response_class=HTMLResponse)
def movie_detail(
    movie_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    detail = get_movie_detail(db, movie_id)
    if detail is None:
        return TEMPLATES.TemplateResponse(
            request,
            "movie_detail.html",
            {
                "movie": None,
                "roles": [],
                "similar": [],
                "spotlight_reason": None,
            },
            status_code=404,
        )

    spotlight_reason = None
    spotlight_ids = get_daily_spotlight_ids(db, limit=4)
    if detail.id in spotlight_ids:
        spotlight_reason = build_spotlight_reason(detail)

    return TEMPLATES.TemplateResponse(
        request,
        "movie_detail.html",
        {
            "movie": detail,
            "roles": detail.roles,
            "similar": detail.similar,
            "spotlight_reason": spotlight_reason,
        },
    )
