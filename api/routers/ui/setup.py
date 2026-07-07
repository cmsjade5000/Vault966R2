from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.services.profiles import set_active_profile_cookie
from api.services.session import SESSION_COOKIE_NAME, create_session_token, get_session_secret
from api.services.setup import SetupError, create_first_profile_setup, is_setup_complete
from api.services.ui.templates import TEMPLATES

router = APIRouter()


def _render_setup(
    request: Request,
    *,
    error: str | None = None,
    profile_name: str = "",
    status_code: int = 200,
):
    return TEMPLATES.TemplateResponse(
        request,
        "setup.html",
        {
            "error": error,
            "profile_name": profile_name,
        },
        status_code=status_code,
    )


@router.get("/setup", response_class=HTMLResponse)
def setup_ui(request: Request, db: Session = Depends(get_db)):
    if is_setup_complete(db):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return _render_setup(request)


@router.post("/setup", response_class=HTMLResponse)
def setup_submit(
    request: Request,
    profile_name: str = Form(default="", max_length=80),
    access_key: str = Form(default="", max_length=128),
    passcode: str = Form(default="", max_length=128),
    passcode_confirm: str = Form(default="", max_length=128),
    db: Session = Depends(get_db),
):
    try:
        result = create_first_profile_setup(
            db,
            profile_name=profile_name,
            access_key=access_key,
            passcode=passcode,
            passcode_confirm=passcode_confirm,
        )
    except SetupError as exc:
        return _render_setup(
            request,
            error=str(exc),
            profile_name=profile_name,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    ttl_seconds = settings.login_session_ttl_hours * 60 * 60
    token = create_session_token(
        result.profile.id,
        secret=get_session_secret(settings.login_session_secret),
        ttl_seconds=ttl_seconds,
    )
    response = RedirectResponse(
        url="/ui/onboarding/import",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    set_active_profile_cookie(response, result.profile.id)
    return response
