from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.services.movie_match import (
    QUESTIONS,
    build_match_result,
    next_answer_query,
    previous_answers,
)
from api.services.profiles import (
    get_active_profile_id,
    get_preferences_for_movies,
)
from api.services.ui.grid import attach_genre_display, attach_poster_themes
from api.services.ui.templates import TEMPLATES

router = APIRouter()


@router.get("/ui/match", response_class=HTMLResponse)
def movie_match(
    request: Request,
    answers: Optional[str] = Query(default=None, max_length=120),
    reroll: int = Query(default=0, ge=0, le=50),
    db: Session = Depends(get_db),
):
    result = build_match_result(db, answer_ids=answers, reroll=reroll)
    matched_movies = []
    if result.lead is not None:
        matched_movies.append(result.lead.movie)
    matched_movies.extend(match.movie for match in result.supporting)

    if matched_movies:
        attach_poster_themes(matched_movies)
        attach_genre_display(matched_movies)
        movie_ids = {movie.id for movie in matched_movies if movie.id is not None}
        preferences = get_preferences_for_movies(db, get_active_profile_id(request, db), movie_ids)
        for movie in matched_movies:
            pref = preferences.get(movie.id, {}) if movie.id is not None else {}
            setattr(movie, "liked", pref.get("liked", False))
            setattr(movie, "watchlist", pref.get("watchlist", False))

    back_answers = previous_answers(result.answers)
    context = {
        "questions": QUESTIONS,
        "result": result,
        "answers_query": ",".join(result.answers),
        "back_answers_query": ",".join(back_answers),
        "next_answer_query": next_answer_query,
        "reroll": reroll,
    }
    return TEMPLATES.TemplateResponse(request, "movies_match.html", context)
