from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, selectinload

from api.db import get_db
from api.models.movie import Movie
from api.services.ui.templates import TEMPLATES

router = APIRouter()


@router.get("/ui/movies/top", response_class=HTMLResponse)
def movies_top(request: Request, db: Session = Depends(get_db)):
    imdb_leaders = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.imdb_rating.isnot(None))
        .order_by(
            Movie.imdb_rating.desc(),
            Movie.imdb_votes.desc().nullslast(),
            Movie.title.asc(),
        )
        .limit(50)
        .all()
    )

    rt_leaders = (
        db.query(Movie)
        .options(selectinload(Movie.genres))
        .filter(Movie.rt_score.isnot(None))
        .order_by(
            Movie.rt_score.desc(),
            Movie.imdb_votes.desc().nullslast(),
            Movie.title.asc(),
        )
        .limit(50)
        .all()
    )

    context = {
        "request": request,
        "top_imdb": imdb_leaders,
        "top_rt": rt_leaders,
    }
    return TEMPLATES.TemplateResponse("movies_top.html", context)
