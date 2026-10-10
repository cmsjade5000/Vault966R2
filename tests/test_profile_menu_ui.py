"""Synthetic account navigation only; never changes real preferences or credentials."""

from html.parser import HTMLParser

import pytest

from api.models.profile import ProfileCredential
from api.services.session import SESSION_COOKIE_NAME
from tests.setup_support import local_browser
from tests.test_personal_login import owner, signin, ORIGIN, PASSWORD


class AccountNavigation(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.primary = []
        self.account = []
        self.logout = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        context = self.stack[-1][1] if self.stack else ""
        if attrs.get("id") == "primary-nav":
            context = "primary"
        elif "data-profile-menu" in attrs:
            context = "account"
        if tag == "a":
            if context == "primary":
                self.primary.append(attrs.get("href"))
            elif context == "account":
                self.account.append(attrs.get("href"))
        if tag == "form" and context == "account":
            self.logout.append((attrs.get("method"), attrs.get("action")))
        if tag not in {
            "meta",
            "link",
            "input",
            "img",
            "br",
            "hr",
            "source",
            "path",
            "circle",
            "rect",
        }:
            self.stack.append((tag, context))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


@pytest.fixture
def client(client):
    with local_browser() as local:
        yield local


def test_admin_account_actions_move_out_of_primary_navigation(client, monkeypatch):
    owner(client, monkeypatch)
    page = client.get("/ui/movies")
    assert page.status_code == 200
    nav = AccountNavigation(page.text)
    assert nav.account == ["/ui/switch-person", "/ui/profiles/new"]
    assert nav.logout == [("post", "/logout")]
    assert "/ui/switch-person" not in nav.primary and "/ui/profiles/new" not in nav.primary
    assert nav.primary == [
        "/ui/movies",
        "/ui/discover",
        "/ui/match",
        "/ui/watchlist",
        "/ui/movies/health",
    ]
    assert 'aria-controls="profile-menu-panel"' in page.text
    assert "js/profile_menu.js?v=" in page.text


def test_reviewer_menu_hides_enrollment_and_backend_keeps_role_gate(
    client, db_session, monkeypatch
):
    owner(client, monkeypatch)
    added = client.post(
        "/ui/profiles/new",
        headers=ORIGIN,
        data={
            "profile_name": "Synthetic reviewer",
            "passcode": PASSWORD,
            "passcode_confirm": PASSWORD,
        },
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert signin(client, name="Synthetic reviewer").status_code == 200
    nav = AccountNavigation(client.get("/ui/discover").text)
    assert nav.account == ["/ui/switch-person"]
    assert "/ui/movies/health" not in nav.primary
    assert nav.logout == [("post", "/logout")]
    assert client.get("/ui/profiles/new").status_code == 403
    assert client.post("/ui/profiles/new", headers=ORIGIN, data={}).status_code == 403
    assert db_session.query(ProfileCredential).count() == 2


def test_menu_switch_requires_credentials_and_cancel_keeps_existing_session(client, monkeypatch):
    owner(client, monkeypatch)
    cookie = client.cookies.get(SESSION_COOKIE_NAME)
    page = client.get("/ui/switch-person")
    assert page.status_code == 200 and 'href="/ui/movies"' in page.text
    failed = signin(client, route="/ui/switch-person", name="Someone else", password="incorrect")
    assert failed.status_code == 401
    assert client.cookies.get(SESSION_COOKIE_NAME) == cookie
    assert client.get("/ui/movies").status_code == 200
    assert AccountNavigation(client.get("/ui/movies").text).account == [
        "/ui/switch-person",
        "/ui/profiles/new",
    ]


def test_signed_out_page_has_no_profile_actions(client, monkeypatch):
    owner(client, monkeypatch)
    client.cookies.clear()
    page = client.get("/login")
    assert page.status_code == 200
    assert "data-profile-menu" not in page.text
    assert "js/profile_menu.js" not in page.text
