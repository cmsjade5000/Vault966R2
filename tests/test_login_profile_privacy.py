"""Personal sign-in must never render the legacy shared-profile picker."""

import pytest
from starlette.requests import Request

from api.config import settings
from api.models.profile import AppSetup, ProfileCredential
from api.routers.ui import login as login_router
from api.services.login_throttle import LoginAttemptLimiter
from api.services.profiles import get_profiles
from api.services.session import SESSION_COOKIE_NAME
from tests.setup_support import authorize_setup, local_browser
from tests.test_setup import _clear_legacy_credentials

ORIGIN = {"Origin": "http://127.0.0.1"}
OWNER = "Synthetic Private Owner"
REVIEWER = "Synthetic Private Reviewer"
PASSWORD = "synthetic-password-only"


@pytest.fixture
def client(client):
    with local_browser() as local:
        yield local


@pytest.fixture
def personal_profiles(client, db_session, monkeypatch):
    _clear_legacy_credentials(monkeypatch)
    monkeypatch.setattr(login_router, "login_attempt_limiter", LoginAttemptLimiter())
    authorize_setup(client, owner_name=OWNER)
    for route, name in (("/setup", OWNER), ("/ui/profiles/new", REVIEWER)):
        response = client.post(
            route,
            headers=ORIGIN,
            data={"profile_name": name, "passcode": PASSWORD, "passcode_confirm": PASSWORD},
            follow_redirects=False,
        )
        assert response.status_code == 303
    return {profile.name: profile.id for profile in get_profiles(db_session)}


def assert_no_profile_picker(response, names):
    for name in names:
        assert name not in response.text
    assert 'name="profile_id"' not in response.text
    assert "login-profile-form" not in response.text
    assert "Shared access is verified" not in response.text
    assert 'data-unlocked="0"' in response.text


@pytest.mark.parametrize(
    "personal_mode,switching", [(True, False), (True, True), (False, True), (None, False)]
)
def test_login_context_strips_all_picker_state(db_session, monkeypatch, personal_mode, switching):
    profiles = get_profiles(db_session)
    if personal_mode is not None:
        db_session.add(AppSetup(id=1, completed=True, personal_sign_in_only=personal_mode))
        db_session.commit()
    monkeypatch.setattr(login_router, "_public_archive_posters", lambda request: [])
    context = login_router._login_template_context(
        Request({"type": "http"}),
        profiles,
        db=db_session if personal_mode is not None else None,
        active_profile_id=profiles[0].id,
        default_profile_id=profiles[0].id,
        unlocked=True,
        switching=switching,
    )
    assert context["profiles"] == []
    assert context["profile_options"] == []
    assert context["active_profile_id"] is None
    assert context["default_profile_id"] is None
    assert context["unlocked"] is False


@pytest.mark.parametrize("route", ["/login", "/login?unlocked=1", "/ui/switch-person"])
def test_personal_login_pages_hide_profiles(client, personal_profiles, route):
    if route != "/ui/switch-person":
        client.cookies.clear()
        client.cookies.set("vault_profile_id", str(personal_profiles[REVIEWER]))
        client.cookies.set("vault_unlock", login_router._create_unlock_token(None))
    response = client.get(route)
    assert response.status_code == 200
    assert_no_profile_picker(response, personal_profiles)


@pytest.mark.parametrize("cookie_value", ["999999", "0", "-1", "01", "invalid"])
def test_personal_login_does_not_reveal_profile_ids_in_cookies(
    client, personal_profiles, cookie_value
):
    client.cookies.clear()
    client.cookies.set("vault_profile_id", cookie_value)
    response = client.get("/login")
    assert response.status_code == 200
    assert_no_profile_picker(response, personal_profiles)
    assert "vault_profile_id" not in response.cookies


@pytest.mark.parametrize("route", ["/login", "/ui/switch-person"])
@pytest.mark.parametrize("accept", ["*/*", "text/html"])
def test_personal_invalid_and_throttled_html_hide_profiles(
    client, personal_profiles, route, accept
):
    if route == "/login":
        client.cookies.clear()
    session_before = client.cookies.get(SESSION_COOKIE_NAME)
    for expected_status in [401] * 5 + [429]:
        response = client.post(
            route,
            headers={**ORIGIN, "Accept": accept},
            data={"access_key": "missing", "passcode": "incorrect"},
            follow_redirects=False,
        )
        assert response.status_code == expected_status
        assert_no_profile_picker(response, personal_profiles)
        assert client.cookies.get(SESSION_COOKIE_NAME) == session_before
        assert client.cookies.get("vault_unlock") is None


@pytest.mark.parametrize("unknown_profile", [False, True])
def test_personal_profile_selection_errors_hide_profiles(
    client, personal_profiles, unknown_profile
):
    client.cookies.clear()
    profile_id = (
        max(personal_profiles.values()) + 100 if unknown_profile else personal_profiles[REVIEWER]
    )
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"access_key": OWNER, "passcode": PASSWORD, "profile_id": profile_id},
        follow_redirects=False,
    )
    assert response.status_code == (400 if unknown_profile else 403)
    assert_no_profile_picker(response, personal_profiles)
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    assert client.cookies.get("vault_unlock") is None


@pytest.mark.parametrize(
    "method,route", [("GET", "/login"), ("POST", "/login"), ("POST", "/ui/switch-person")]
)
def test_personal_credentials_unavailable_hide_profiles(
    client, db_session, personal_profiles, method, route
):
    db_session.query(ProfileCredential).delete()
    db_session.commit()
    if route == "/login":
        client.cookies.clear()
    response = client.request(method, route, headers=ORIGIN, follow_redirects=False)
    assert response.status_code == 503
    assert "Login credentials are not configured." in response.text
    assert_no_profile_picker(response, personal_profiles)


def test_legacy_switch_error_hides_picker_but_shared_login_keeps_it(
    client, db_session, monkeypatch
):
    _clear_legacy_credentials(monkeypatch)
    monkeypatch.setattr(login_router, "login_attempt_limiter", LoginAttemptLimiter())
    monkeypatch.setattr(settings, "login_access_key_user_a", "synthetic-personal")
    monkeypatch.setattr(settings, "login_passcode_user_a", PASSWORD)
    monkeypatch.setattr(settings, "login_access_key", "synthetic-shared")
    monkeypatch.setattr(settings, "login_passcode", PASSWORD)
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"access_key": "synthetic-personal", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    session_before = client.cookies.get(SESSION_COOKIE_NAME)
    assert session_before
    response = client.post(
        "/ui/switch-person",
        headers=ORIGIN,
        data={"access_key": "synthetic-shared", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert_no_profile_picker(response, [profile.name for profile in get_profiles(db_session)])
    assert client.cookies.get(SESSION_COOKIE_NAME) == session_before

    client.cookies.clear()
    response = client.post(
        "/login",
        headers=ORIGIN,
        data={"access_key": "synthetic-shared", "passcode": PASSWORD},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login?unlocked=1"
    assert client.cookies.get(SESSION_COOKIE_NAME) is None
    response = client.get(response.headers["location"])
    assert response.status_code == 200
    assert 'data-unlocked="1"' in response.text
    for profile in get_profiles(db_session):
        assert profile.name in response.text
        assert f'name="profile_id" value="{profile.id}"' in response.text
