from fastapi.testclient import TestClient

from api.config import settings
from api.models.profile import AppSetup, Profile, ProfileCredential
from api.services.session import SESSION_COOKIE_NAME, get_session_secret, parse_session_token

SAME_ORIGIN_HEADERS = {"Origin": "http://testserver"}


def _clear_legacy_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", None)
    monkeypatch.setattr(settings, "login_passcode", None)
    monkeypatch.setattr(settings, "login_access_key_user_a", None)
    monkeypatch.setattr(settings, "login_passcode_user_a", None)
    monkeypatch.setattr(settings, "login_access_key_user_b", None)
    monkeypatch.setattr(settings, "login_passcode_user_b", None)


def test_first_run_routes_to_setup_before_login(
    client: TestClient,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)

    login = client.get("/login", follow_redirects=False)
    library = client.get("/ui/movies", follow_redirects=False)
    setup = client.get("/setup")

    assert login.status_code == 302
    assert login.headers["location"] == "/setup"
    assert library.status_code == 302
    assert library.headers["location"] == "/setup"
    assert setup.status_code == 200
    assert "Start Vault 966" in setup.text
    assert "Confirm passcode" in setup.text


def test_setup_creates_admin_profile_hashed_credentials_and_session(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)

    response = client.post(
        "/setup",
        data={
            "profile_name": "Cory",
            "access_key": "vault",
            "passcode": "9660",
            "passcode_confirm": "9660",
        },
        headers=SAME_ORIGIN_HEADERS,
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/onboarding/import"
    profile = db_session.query(Profile).filter(Profile.name == "Cory").one()
    assert profile.role == "admin"
    setup = db_session.get(AppSetup, 1)
    assert setup is not None
    assert setup.completed is True
    assert setup.owner_profile_id == profile.id
    credential = (
        db_session.query(ProfileCredential).filter(ProfileCredential.profile_id == profile.id).one()
    )
    assert credential.access_key_hash != "vault"
    assert credential.passcode_hash != "9660"
    assert credential.access_key_salt
    assert credential.passcode_salt
    token = response.cookies.get(SESSION_COOKIE_NAME)
    session = parse_session_token(token, secret=get_session_secret(settings.login_session_secret))
    assert session is not None
    assert session.profile_id == profile.id


def test_setup_rejects_mismatched_passcode_without_echoing_secret(
    client: TestClient,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)

    response = client.post(
        "/setup",
        data={
            "profile_name": "Cory",
            "access_key": "vault",
            "passcode": "9660",
            "passcode_confirm": "wrong",
        },
        headers=SAME_ORIGIN_HEADERS,
    )

    assert response.status_code == 400
    assert "Passcodes do not match." in response.text
    assert "9660" not in response.text
    assert "wrong" not in response.text


def test_setup_is_unavailable_after_completion_and_db_login_works(
    client: TestClient,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)
    created = client.post(
        "/setup",
        data={
            "profile_name": "Cory",
            "access_key": "vault",
            "passcode": "9660",
            "passcode_confirm": "9660",
        },
        headers=SAME_ORIGIN_HEADERS,
        follow_redirects=False,
    )
    assert created.status_code == 303
    client.cookies.clear()

    setup = client.get("/setup", follow_redirects=False)
    unlock = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "9660"},
        headers={"Accept": "application/json"},
    )
    profile = client.post(
        "/login",
        data={"profile_id": "1"},
        headers={"Accept": "application/json"},
    )

    assert setup.status_code == 302
    assert setup.headers["location"] == "/login"
    assert unlock.status_code == 200
    assert unlock.json() == {"unlocked": True}
    assert profile.status_code == 200
    assert profile.json() == {"ok": True, "redirect_url": "/ui/movies"}


def test_setup_rejects_missing_or_cross_origin_posts_without_processing_credentials(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)
    payload = {
        "profile_name": "Attacker",
        "access_key": "stolen-vault",
        "passcode": "stolen-9660",
        "passcode_confirm": "stolen-9660",
    }

    missing_origin = client.post("/setup", data=payload)
    cross_origin = client.post(
        "/setup",
        data=payload,
        headers={"Origin": "http://evil.test"},
    )

    assert missing_origin.status_code == 403
    assert cross_origin.status_code == 403
    assert "stolen-vault" not in missing_origin.text
    assert "stolen-9660" not in cross_origin.text
    assert db_session.query(ProfileCredential).count() == 0
    assert db_session.get(AppSetup, 1) is None


def test_setup_origin_protection_remains_enabled_when_auth_is_disabled(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "disable_auth", True)

    response = client.post(
        "/setup",
        data={
            "profile_name": "Attacker",
            "access_key": "stolen-vault",
            "passcode": "stolen-9660",
            "passcode_confirm": "stolen-9660",
        },
        headers={"Origin": "http://evil.test"},
    )

    assert response.status_code == 403
    assert "stolen-vault" not in response.text
    assert "stolen-9660" not in response.text
    assert db_session.query(ProfileCredential).count() == 0
    assert db_session.get(AppSetup, 1) is None


def test_completed_setup_rejects_repeat_same_origin_post(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _clear_legacy_credentials(monkeypatch)
    first = client.post(
        "/setup",
        data={
            "profile_name": "Cory",
            "access_key": "vault",
            "passcode": "9660",
            "passcode_confirm": "9660",
        },
        headers=SAME_ORIGIN_HEADERS,
        follow_redirects=False,
    )

    repeated = client.post(
        "/setup",
        data={
            "profile_name": "Mallory",
            "access_key": "replacement",
            "passcode": "0000",
            "passcode_confirm": "0000",
        },
        headers=SAME_ORIGIN_HEADERS,
    )

    assert first.status_code == 303
    assert repeated.status_code == 400
    assert "setup is already complete" in repeated.text
    assert "replacement" not in repeated.text
    assert db_session.query(ProfileCredential).count() == 1
    assert db_session.query(Profile).filter(Profile.name == "Mallory").count() == 0
