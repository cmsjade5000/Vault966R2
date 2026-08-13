from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse

from api.deps.auth import require_profile_role
from api.schemas.common import FOUND_REDIRECT_RESPONSES
from api.services.profiles import ROLE_ADMIN

router = APIRouter(tags=["ui"])


@router.get(
    "/ui/flags",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    responses=FOUND_REDIRECT_RESPONSES,
)
def list_flags_ui(
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
) -> RedirectResponse:
    # Compatibility alias for older bookmarks and generated clients. The Health
    # workbench owns the current flags UI.
    return RedirectResponse(
        url="/ui/movies/health?view=flags#review-workbench",
        status_code=302,
    )
