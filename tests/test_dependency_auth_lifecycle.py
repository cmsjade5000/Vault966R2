"""Dependency releases must retain the installed personal-auth lifecycle boundary.

Every identity, password and signing key here is invented; no deployed state is used.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest

from api.config import settings
from api.models.profile import AppSetup, Profile, ProfileCredential
from api.services.credentials import build_profile_credential
from api.services.profiles import get_profiles
from api.services.session import SESSION_COOKIE_NAME, create_session_token
from api.services.setup import db_credentials_configured, matching_db_credential_profile_id

SECRET = "synthetic-dependency-lifecycle-signing-key-only"
PASSWORD = "synthetic-dependency-lifecycle-password-only"
ORIGIN = {"Origin": "http://testserver", "Accept": "application/json"}


@pytest.fixture
def personal_state(db_session, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", SECRET)
    monkeypatch.setattr(settings, "assistant_access_token", None)
    for name in (
        "login_access_key_user_a",
        "login_passcode_user_a",
        "login_access_key_user_b",
        "login_passcode_user_b",
    ):
        monkeypatch.setattr(settings, name, None)
    monkeypatch.setattr(settings, "login_access_key", "retired-synthetic-shared")
    monkeypatch.setattr(settings, "login_passcode", PASSWORD)
    db_session.add_all(
        [
            Profile(
                id=1,
                name="Archived synthetic admin",
                role="admin",
                archived_at=time_now(),
                session_revision=1,
            ),
            Profile(id=5, name="SyntheticOwner", role="admin", session_revision=2),
            Profile(id=6, name="SyntheticLegacyActive", role="reviewer", session_revision=0),
        ]
    )
    db_session.flush()
    for ident, name in ((1, "RetiredSyntheticOwner"), (5, "SyntheticOwner")):
        db_session.add(
            build_profile_credential(profile_id=ident, access_key=name, passcode=PASSWORD)
        )
    db_session.add(
        AppSetup(
            id=1, completed=True, owner_profile_id=5, personal_sign_in_only=True, unlock_revision=1
        )
    )
    db_session.commit()
    return db_session


def time_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def legacy_session(profile_id):
    """A correctly signed pre-revision session, made solely with the synthetic key."""
    now = int(time.time())
    payload = {"v": 1, "profile_id": profile_id, "iat": now, "exp": now + 3600}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


@pytest.mark.parametrize("route", ["/login", "/ui/switch-person"])
def test_retained_archived_credentials_cannot_sign_in(client, personal_state, route):
    client.cookies.set(
        SESSION_COOKIE_NAME, create_session_token(5, secret=SECRET, ttl_seconds=3600, revision=2)
    )
    before = client.cookies.get(SESSION_COOKIE_NAME)
    assert (
        matching_db_credential_profile_id(
            personal_state, access_key="RetiredSyntheticOwner", passcode=PASSWORD
        )
        is None
    )
    response = client.post(
        route,
        headers=ORIGIN,
        data={"profile_id": "1", "access_key": "RetiredSyntheticOwner", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert client.cookies.get(SESSION_COOKIE_NAME) == before
    assert personal_state.query(ProfileCredential).count() == 2
    assert [p.id for p in get_profiles(personal_state)] == [5, 6]


@pytest.mark.parametrize("profile_id,revision", [(1, 1), (5, 1), (9999, 0)])
def test_archived_revoked_and_missing_profile_sessions_fail_every_entrypoint(
    client, personal_state, profile_id, revision
):
    client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(profile_id, secret=SECRET, ttl_seconds=3600, revision=revision),
    )
    for path in ("/api/profiles", "/api/assistant"):
        assert client.get(path, follow_redirects=False).status_code == 401
    page = client.get("/ui/movies", follow_redirects=False)
    assert page.status_code == 302 and page.headers["location"] == "/login"
    assert client.get("/login", follow_redirects=False).status_code == 200


@pytest.mark.parametrize("profile_id,accepted", [(1, False), (5, False), (6, True)])
def test_missing_revision_claim_is_only_valid_for_active_revision_zero_profile(
    client, personal_state, profile_id, accepted
):
    client.cookies.set(SESSION_COOKIE_NAME, legacy_session(profile_id))
    assert client.get("/api/profiles").status_code == (200 if accepted else 401)
    assert client.get("/login", follow_redirects=False).status_code == (302 if accepted else 200)


def test_personal_credentials_sign_in_directly_without_profile_selection(client, personal_state):
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"profile_id": "1", "access_key": "SyntheticOwner", "passcode": PASSWORD},
        follow_redirects=False,
    )
    # The explicit profile ID cannot replace the credential owner's identity.
    assert response.status_code == 400
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"access_key": "SyntheticOwner", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.json() == {"ok": True, "redirect_url": "/ui/movies"}
    client.cookies.set("vault_profile_id", "1")
    assert client.get("/api/profiles").json()["active_profile_id"] == 5
    assert client.get("/ui/movies").status_code == 200
    assert client.get("/api/assistant", params={"q": "synthetic", "limit": 1}).status_code == 200


def test_personal_mode_has_no_legacy_unlock_or_environment_credential_fallback(
    client, personal_state
):
    from api.routers.ui.login import _create_unlock_token

    client.cookies.set("vault_unlock", _create_unlock_token(None, revision=1))
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"profile_id": "5", "access_key": "retired-synthetic-shared", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.get("/api/profiles").status_code == 401


def test_only_archived_credentials_do_not_reopen_profiles_or_complete_setup(client, personal_state):
    personal_state.query(ProfileCredential).filter(ProfileCredential.profile_id == 5).delete()
    for profile in personal_state.query(Profile).filter(Profile.archived_at.is_(None)):
        profile.archived_at = time_now()
    personal_state.get(AppSetup, 1).completed = False
    personal_state.commit()
    assert not db_credentials_configured(personal_state)
    assert get_profiles(personal_state) == []
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 302 and response.headers["location"] == "/setup"
    assert personal_state.query(Profile).count() == 3
