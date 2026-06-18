from fastapi.testclient import TestClient

from api.config import settings
from api.services.session import SESSION_COOKIE_NAME, get_session_secret, parse_session_token
from api.services.ui.grid import FILTER_COOKIE_NAME, FILTER_COOKIE_PATH


def test_login_page_only_shows_unlock_action(client: TestClient):
    response = client.get("/login")

    assert response.status_code == 200
    assert 'aria-label="Unlock Vault 966"' in response.text
    assert "data-vault-auto-lock" not in response.text
    assert "js/auto_lock.js" not in response.text
    assert "Vault Username" not in response.text
    assert "Passcode" not in response.text
    assert "Your private film archive is standing by." not in response.text
    assert "Unlock the vault" in response.text
    assert "CORY" in response.text
    assert "DAMIAN" in response.text
    assert (
        'class="login-form"\n        method="post"\n        aria-label="Unlock Vault 966"\n      >'
        in response.text
    )
    assert response.text.count('data-vault-busy-message="Unlocking the Vault…"') == 2
    assert "login-crt" not in response.text
    assert "css/login.css?v=" in response.text
    assert "js/login_archive.js?v=" in response.text


def test_unlock_reveals_profile_picker_without_session(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)

    response = client.post("/login", headers={"Accept": "application/json"})

    assert response.status_code == 200
    assert response.json() == {"unlocked": True}
    assert response.cookies.get(SESSION_COOKIE_NAME) is None

    discover = client.get("/ui/discover", follow_redirects=False)
    assert discover.status_code == 302
    assert discover.headers["location"] == "/login"


def test_profile_tap_creates_selected_profile_session(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)

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

    discover = client.get("/ui/discover")
    assert discover.status_code == 200
    assert 'data-vault-auto-lock-ms="1200000"' in discover.text
    assert "js/auto_lock.js" in discover.text


def test_profile_form_redirects_without_javascript(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "disable_auth", False)
    monkeypatch.setattr(settings, "login_session_secret", None)

    response = client.post(
        "/login",
        data={"profile_id": "1"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/movies"
    assert response.cookies.get(SESSION_COOKIE_NAME)


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
