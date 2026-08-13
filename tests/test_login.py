from fastapi.testclient import TestClient

from api.config import settings
from api.models.movie import Movie
from api.models.profile import Profile
from api.services.profiles import get_profiles
from api.services.session import SESSION_COOKIE_NAME, get_session_secret, parse_session_token
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH
from api.routers.ui.login import UNLOCK_COOKIE_NAME, _create_unlock_token


def test_login_page_only_shows_unlock_action(client: TestClient):
    response = client.get("/login")

    assert response.status_code == 200
    assert 'aria-label="Unlock Vault 966"' in response.text
    assert "data-vault-auto-lock" not in response.text
    assert "js/auto_lock.js" not in response.text
    assert "Access key" in response.text
    assert "Passcode" in response.text
    assert "Your private film archive is standing by." not in response.text
    assert "Unlock the vault" in response.text
    assert "User A" in response.text
    assert "User B" in response.text
    assert 'class="login-form"' in response.text
    assert 'name="access_key"' in response.text
    assert 'name="passcode"' in response.text
    assert response.text.count('data-vault-busy-message="Unlocking the Vault…"') == 2
    assert "login-crt" not in response.text
    assert "css/login.css?v=" in response.text
    assert "js/login_archive.js?v=" in response.text


def test_public_login_uses_static_archive_art(
    client: TestClient,
    db_session,
) -> None:
    private_poster_url = "https://collection.example/private-poster.jpg"
    movie = db_session.query(Movie).filter(Movie.title == "Blade Runner").one()
    movie.poster_url = private_poster_url
    db_session.commit()

    response = client.get("/login")

    assert response.status_code == 200
    assert private_poster_url not in response.text
    assert 'src="http://testserver/static/img/app-icon.png"' in response.text
    assert '"http://testserver/static/img/app-icon.png"' in response.text
    assert "collection.example" not in response.text


def test_default_profiles_are_placeholder_names(db_session) -> None:
    db_session.query(Profile).delete()
    db_session.add_all(
        [
            Profile(name="Private Name 1", role="reviewer"),
            Profile(name="Private Name 2", role="reviewer"),
        ]
    )
    db_session.commit()

    profiles = get_profiles(db_session)

    assert [(profile.name, profile.role) for profile in profiles[:2]] == [
        ("User A", "admin"),
        ("User B", "reviewer"),
    ]


def test_unlock_reveals_profile_picker_without_session(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    response = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "966"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"unlocked": True}
    assert response.cookies.get(SESSION_COOKIE_NAME) is None

    discover = client.get("/ui/discover", follow_redirects=False)
    assert discover.status_code == 302
    assert discover.headers["location"] == "/login"


def test_profile_tap_creates_selected_profile_session(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    unlock = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "966"},
        headers={"Accept": "application/json"},
    )
    assert unlock.status_code == 200

    response = client.post(
        "/login",
        data={"profile_id": "2"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "redirect_url": "/ui/movies"}
    token = response.cookies.get(SESSION_COOKIE_NAME)
    session = parse_session_token(
        token,
        secret=get_session_secret(settings.login_session_secret),
    )
    assert session is not None
    assert session.profile_id == 2

    discover = client.get("/ui/discover", follow_redirects=False)
    assert discover.status_code == 200
    assert "Watch Tonight" in discover.text


def test_profile_form_redirects_without_javascript(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    response = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "966"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?unlocked=1"
    assert response.cookies.get(SESSION_COOKIE_NAME) is None

    response = client.post(
        "/login",
        data={"profile_id": "1"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/movies"
    assert response.cookies.get(SESSION_COOKIE_NAME)


def test_login_rejects_invalid_credentials(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    response = client.post(
        "/login",
        data={"profile_id": "1", "access_key": "vault", "passcode": "wrong"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Invalid login credentials."}
    assert response.cookies.get(SESSION_COOKIE_NAME) is None


def test_login_throttles_failed_credential_checks_and_preserves_success(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    for _ in range(4):
        rejected = client.post(
            "/login",
            data={"access_key": "vault", "passcode": "wrong"},
            headers={"Accept": "application/json"},
        )
        assert rejected.status_code == 401

    unlocked = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "966"},
        headers={"Accept": "application/json"},
    )
    assert unlocked.status_code == 200
    assert unlocked.json() == {"unlocked": True}
    client.cookies.clear()

    for _ in range(5):
        rejected = client.post(
            "/login",
            data={"access_key": "vault", "passcode": "wrong"},
            headers={"Accept": "application/json"},
        )
        assert rejected.status_code == 401

    throttled = client.post(
        "/login",
        data={"access_key": "vault", "passcode": "wrong"},
        headers={"Accept": "application/json"},
    )
    assert throttled.status_code == 429
    assert throttled.json() == {"error": "Too many login attempts. Try again shortly."}


def test_login_throttle_does_not_block_unlock_cookie_profile_selection(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")

    for _ in range(5):
        rejected = client.post(
            "/login",
            data={"access_key": "vault", "passcode": "wrong"},
            headers={"Accept": "application/json"},
        )
        assert rejected.status_code == 401

    profile = client.post(
        "/login",
        data={"profile_id": "1"},
        headers={
            "Accept": "application/json",
            "Cookie": f"{UNLOCK_COOKIE_NAME}={_create_unlock_token(None)}",
        },
    )
    assert profile.status_code == 200
    assert profile.json() == {"ok": True, "redirect_url": "/ui/movies"}


def test_login_error_uses_static_archive_art(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", "vault")
    monkeypatch.setattr(settings, "login_passcode", "966")
    private_poster_url = "https://collection.example/error-poster.jpg"
    movie = db_session.query(Movie).filter(Movie.title == "The Matrix").one()
    movie.poster_url = private_poster_url
    db_session.commit()

    response = client.post(
        "/login",
        data={"profile_id": "1", "access_key": "vault", "passcode": "wrong"},
    )

    assert response.status_code == 401
    assert "Invalid login credentials." in response.text
    assert private_poster_url not in response.text
    assert 'src="http://testserver/static/img/app-icon.png"' in response.text
    assert "collection.example" not in response.text


def test_login_fails_closed_when_credentials_missing(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)
    monkeypatch.setattr(settings, "login_access_key", None)
    monkeypatch.setattr(settings, "login_passcode", None)
    monkeypatch.setattr(settings, "login_access_key_user_a", None)
    monkeypatch.setattr(settings, "login_passcode_user_a", None)
    monkeypatch.setattr(settings, "login_access_key_user_b", None)
    monkeypatch.setattr(settings, "login_passcode_user_b", None)

    response = client.post(
        "/login",
        data={"profile_id": "1"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 503
    assert response.json() == {"error": "Login credentials are not configured."}
    assert response.cookies.get(SESSION_COOKIE_NAME) is None


def test_logout_clears_saved_library_search(client: TestClient) -> None:
    searched = client.get("/ui/movies", params={"q": "Titanic"})
    assert searched.status_code == 200
    assert client.cookies.get(FILTER_COOKIE_NAME) is not None

    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert client.cookies.get(FILTER_COOKIE_NAME) is None
    set_cookie = response.headers["set-cookie"]
    assert f'{FILTER_COOKIE_NAME}=""' in set_cookie
    assert f"Path={FILTER_COOKIE_PATH}" in set_cookie
