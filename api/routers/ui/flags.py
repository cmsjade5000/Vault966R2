from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from api.db import get_db
from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.ui.templates import TEMPLATES

router = APIRouter(tags=["ui"])


@router.get("/ui/flags", response_class=HTMLResponse)
def list_flags_ui(request: Request, db: Session = Depends(get_db)):
    flags = (
        db.query(MovieFlag)
        .options(joinedload(MovieFlag.movie).joinedload(Movie.genres))
        .order_by(desc(MovieFlag.updated_at))
        .all()
    )
    return TEMPLATES.TemplateResponse(
        request,
        "flags.html",
        {"flags": flags},
    )
