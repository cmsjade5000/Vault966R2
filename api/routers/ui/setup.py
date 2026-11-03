from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, HTTPException, status
from ipaddress import ip_address
import secrets
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.deps.auth import require_strict_same_origin, require_profile_role
from api.services.profiles import set_active_profile_cookie, ROLE_ADMIN
from api.services.session import SESSION_COOKIE_NAME, create_session_token, get_session_secret
from api.services.setup import (
    SetupError,
    create_first_profile_setup,
    create_personal_reviewer,
    is_setup_complete,
    setup_record,
)
from api.routers.ui.login import _login_template_context
from api.services.login_throttle import LoginAttemptLimiter
from api.services.setup_grants import (
    SETUP_BROWSER_COOKIE,
    SETUP_COOKIE_PATH,
    GRANT_TTL_SECONDS,
    SetupGrantError,
    bind_setup_grant,
    require_bound_setup_grant,
)

claim_attempt_limiter = LoginAttemptLimiter()
from api.services.ui.templates import TEMPLATES

router = APIRouter()


def _render_setup(
    request: Request,
    *,
    error: str | None = None,
    profile_name: str = "",
    status_code: int = 200,
    enrollment: bool = False,
    created: bool = False,
):
    response = TEMPLATES.TemplateResponse(
        request,
        "setup.html",
        {
            **_login_template_context(request, []),
            "enrollment": enrollment,
            "created": created,
            "form_action": "/ui/profiles/new" if enrollment else "/setup",
            "error": error,
            "profile_name": profile_name,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    # Ordinary form POSTs send Origin: null under no-referrer. Keep the
    # same-origin CSRF signal while withholding referrers from other origins.
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def _require_local_setup(request: Request, db: Session, *, always: bool = False) -> None:
    record = setup_record(db)
    if not always and (record is None or not record.local_setup_only):
        return
    try:
        local = bool(request.client and ip_address(request.client.host).is_loopback)
    except ValueError:
        local = False
    forwarded = any(
        name == "forwarded" or name.startswith("x-forwarded-") for name in request.headers
    )
    if forwarded or not local or request.url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(
            status_code=403, detail="Complete account setup directly on this Mac using localhost."
        )


@router.get("/setup", response_class=HTMLResponse)
def setup_ui(request: Request, db: Session = Depends(get_db)):
    if is_setup_complete(db):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    _require_local_setup(request, db, always=True)
    try:
        grant = require_bound_setup_grant(
            db, browser_nonce=request.cookies.get(SETUP_BROWSER_COOKIE)
        )
    except SetupGrantError:
        return RedirectResponse("/setup/claim", status_code=303)
    return _render_setup(request, profile_name=grant.owner_name)


@router.post("/setup", response_class=HTMLResponse)
def setup_submit(
    request: Request,
    profile_name: str = Form(default="", max_length=80),
    access_key: str = Form(default="", max_length=128),
    passcode: str = Form(default="", max_length=128),
    passcode_confirm: str = Form(default="", max_length=128),
    db: Session = Depends(get_db),
    _: None = Depends(require_strict_same_origin),
):
    _require_local_setup(request, db, always=True)
    try:
        require_bound_setup_grant(db, browser_nonce=request.cookies.get(SETUP_BROWSER_COOKIE))
    except SetupGrantError:
        raise HTTPException(status_code=403, detail="Private setup claim required.")
    try:
        result = create_first_profile_setup(
            db,
            profile_name=profile_name,
            access_key=profile_name,
            passcode=passcode,
            passcode_confirm=passcode_confirm,
            bootstrap_browser_nonce=request.cookies.get(SETUP_BROWSER_COOKIE),
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
        revision=result.profile.session_revision,
    )
    response = RedirectResponse(
        url="/ui/movies",
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
    response.delete_cookie(SETUP_BROWSER_COOKIE, path=SETUP_COOKIE_PATH)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/ui/profiles/new", response_class=HTMLResponse)
def enroll_person_ui(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
):
    _require_local_setup(request, db)
    return _render_setup(
        request, enrollment=True, created=request.query_params.get("created") == "1"
    )


@router.post("/ui/profiles/new", response_class=HTMLResponse)
def enroll_person_submit(
    request: Request,
    profile_name: str = Form(default="", max_length=80),
    passcode: str = Form(default="", max_length=128),
    passcode_confirm: str = Form(default="", max_length=128),
    db: Session = Depends(get_db),
    _: str = Depends(require_profile_role(ROLE_ADMIN)),
    _origin: None = Depends(require_strict_same_origin),
):
    _require_local_setup(request, db)
    try:
        create_personal_reviewer(
            db, profile_name=profile_name, passcode=passcode, passcode_confirm=passcode_confirm
        )
    except SetupError as exc:
        return _render_setup(
            request, enrollment=True, error=str(exc), profile_name=profile_name, status_code=400
        )
    return RedirectResponse(url="/ui/profiles/new?created=1", status_code=303)


def _render_claim(request: Request, *, error: bool = False, status_code: int = 200):
    response = TEMPLATES.TemplateResponse(
        request,
        "setup_claim.html",
        {
            **_login_template_context(request, []),
            "error": error,
        },
        status_code=status_code,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@router.get("/setup/claim", response_class=HTMLResponse)
def setup_claim_ui(request: Request, db: Session = Depends(get_db)):
    if is_setup_complete(db):
        return RedirectResponse("/login", status_code=302)
    _require_local_setup(request, db, always=True)
    try:
        require_bound_setup_grant(db, browser_nonce=request.cookies.get(SETUP_BROWSER_COOKIE))
        return RedirectResponse("/setup", status_code=303)
    except SetupGrantError:
        pass
    response = _render_claim(request)
    response.set_cookie(
        SETUP_BROWSER_COOKIE,
        secrets.token_urlsafe(32),
        max_age=GRANT_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path=SETUP_COOKIE_PATH,
    )
    return response


@router.post("/setup/claim", response_class=HTMLResponse)
def setup_claim_submit(
    request: Request,
    setup_code: str = Form(default="", max_length=128),
    db: Session = Depends(get_db),
    _: None = Depends(require_strict_same_origin),
):
    _require_local_setup(request, db, always=True)
    if is_setup_complete(db):
        raise HTTPException(status_code=403, detail="Private setup is unavailable.")
    client_key = request.client.host if request.client else None
    if client_key is None or not claim_attempt_limiter.begin_attempt(client_key):
        return _render_claim(request, error=True, status_code=429)
    try:
        bind_setup_grant(
            db, code=setup_code, browser_nonce=request.cookies.get(SETUP_BROWSER_COOKIE)
        )
    except SetupGrantError:
        claim_attempt_limiter.record_failure(client_key)
        return _render_claim(request, error=True, status_code=403)
    except Exception:
        claim_attempt_limiter.cancel_attempt(client_key)
        raise
    claim_attempt_limiter.clear(client_key)
    response = RedirectResponse("/setup", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "same-origin"
    return response
