from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.services.movies_detail import get_movie_detail
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
            "movie_detail.html",
            {
                "request": request,
                "movie": None,
                "roles": [],
                "similar": [],
            },
            status_code=404,
        )

    return TEMPLATES.TemplateResponse(
        "movie_detail.html",
        {
            "request": request,
            "movie": detail,
            "roles": detail.roles,
            "similar": detail.similar,
        },
    )
