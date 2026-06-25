from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps.auth import require_same_origin
from api.services.profiles import get_active_profile_id, get_profiles, set_active_profile_cookie

# Profile endpoints are gated by the login session; profile selection is still
# cookie-scoped, not a full user identity.
router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ActiveProfileRequest(BaseModel):
    profile_id: int = Field(..., ge=1)


@router.get("")
def list_profiles(request: Request, db: Session = Depends(get_db)) -> dict:
    profiles = get_profiles(db)
    active_id = get_active_profile_id(request, db)
    return {
        "profiles": [{"id": profile.id, "name": profile.name} for profile in profiles],
        "active_profile_id": active_id,
    }


@router.post("/active")
def set_active_profile(
    payload: ActiveProfileRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(require_same_origin),
) -> dict:
    session_profile_id = getattr(request.state, "session_profile_id", None)
    if isinstance(session_profile_id, int) and payload.profile_id != session_profile_id:
        raise HTTPException(status_code=403, detail="Profile switching is restricted.")
    profiles = get_profiles(db)
    if not any(profile.id == payload.profile_id for profile in profiles):
        raise HTTPException(status_code=400, detail="Unknown profile")
    set_active_profile_cookie(response, payload.profile_id)
    return {"active_profile_id": payload.profile_id}
