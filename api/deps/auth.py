from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.models.profile import Profile
from api.services.profiles import ROLE_ADMIN, ROLE_REVIEWER, get_active_profile_role

_bearer_scheme = HTTPBearer(auto_error=False)
_provider_work_lock = Lock()
_provider_work_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def admin_bearer_token_valid(request: Request) -> bool:
    token = settings.admin_token
    if not token:
        return False
    scheme, _, candidate = request.headers.get("Authorization", "").partition(" ")
    return scheme.lower() == "bearer" and candidate.strip() == token


def require_same_origin(request: Request) -> None:
    """Reject cross-origin browser mutations while preserving local/test workflows."""
    if settings.disable_auth:
        return
    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Same-origin request required",
        )
    parsed = urlsplit(origin)
    expected_scheme = request.url.scheme
    expected_host = request.headers.get("host", "")
    if parsed.scheme != expected_scheme or parsed.netloc != expected_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request rejected",
        )


def require_provider_work_budget(
    request: Request,
    *,
    scope: str,
    max_requests: int = 10,
    window_seconds: int = 60,
) -> None:
    """Apply a small per-user budget before routes spend provider quota."""
    profile_id = getattr(request.state, "session_profile_id", None)
    if isinstance(profile_id, int) and profile_id > 0:
        actor = f"profile:{profile_id}"
    else:
        client_host = request.client.host if request.client else "unknown"
        actor = f"client:{client_host}"

    now = monotonic()
    cutoff = now - window_seconds
    key = (scope, actor)
    with _provider_work_lock:
        window = _provider_work_windows[key]
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Provider work rate limit exceeded",
            )
        window.append(now)


def require_same_origin_provider_work(
    scope: str,
    *,
    max_requests: int = 10,
    window_seconds: int = 60,
):
    def _checker(request: Request) -> None:
        if not getattr(request.state, "admin_bearer_authorized", False):
            require_same_origin(request)
        require_provider_work_budget(
            request,
            scope=scope,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

    return _checker


def clear_provider_work_budgets_for_tests() -> None:
    with _provider_work_lock:
        _provider_work_windows.clear()


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> None:
    token = settings.admin_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin token not configured",
        )

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or credentials.credentials != token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )

    return None


def require_admin_or_profile_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> None:
    token = settings.admin_token
    if credentials is not None:
        if token and credentials.scheme.lower() == "bearer" and credentials.credentials == token:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )

    if request.method not in _SAFE_METHODS:
        require_same_origin(request)
    profile_id = getattr(request.state, "session_profile_id", None)
    if not isinstance(profile_id, int) or profile_id <= 0:
        if settings.disable_auth:
            role = get_active_profile_role(request, db)
            if role == ROLE_ADMIN:
                request.state.session_profile_role = role
                return None
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin profile session required",
        )

    profile = db.get(Profile, profile_id)
    if getattr(profile, "role", None) != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin profile session required",
        )
    request.state.session_profile_role = ROLE_ADMIN
    return None


def require_profile_role(*allowed_roles: str):
    valid_roles = {ROLE_ADMIN, ROLE_REVIEWER}
    roles = [role for role in allowed_roles if role in valid_roles]
    if not roles:
        roles = [ROLE_ADMIN]

    def _checker(
        request: Request,
        db: Session = Depends(get_db),
    ) -> str:
        profile_id = getattr(request.state, "session_profile_id", None)
        if not isinstance(profile_id, int) or profile_id <= 0:
            if settings.disable_auth:
                role = get_active_profile_role(request, db)
                if role not in roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized for this action",
                    )
                request.state.session_profile_role = role
                return role
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Profile role required",
            )
        profile = db.get(Profile, profile_id)
        role = getattr(profile, "role", None) if profile else None
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this action",
            )
        request.state.session_profile_role = role
        return role

    return _checker
