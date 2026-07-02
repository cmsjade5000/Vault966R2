from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_profile_role, require_same_origin
from api.models.movie import Movie
from api.models.usage_event import UsageEvent
from api.services.profiles import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    get_active_profile_id,
)

router = APIRouter()

EventName = Literal[
    "library_search_submitted",
    "filters_applied",
    "view_changed",
    "movie_details_opened",
    "discover_rail_opened",
    "personalized_recommendations_shown",
    "random_pick_requested",
    "double_feature_requested",
    "preference_toggled",
]
PageName = Literal["library", "discover", "detail", "watchlist"]


class UsageEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: EventName
    page: PageName
    movie_id: int | None = Field(default=None, ge=1)
    context: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")


@router.post("/ui/events", status_code=status.HTTP_204_NO_CONTENT)
def record_usage_event(
    payload: UsageEventCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN, ROLE_REVIEWER)),
    __: None = Depends(require_same_origin),
) -> Response:
    if payload.movie_id is not None and db.get(Movie, payload.movie_id) is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    profile_id = get_active_profile_id(request, db)
    db.add(
        UsageEvent(
            event_name=payload.event_name,
            profile_id=profile_id if profile_id > 0 else None,
            movie_id=payload.movie_id,
            page=payload.page,
            context=payload.context,
        )
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
