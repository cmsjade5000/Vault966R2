"""Login editing contract with synthetic sessions; no physical keyboard claim."""

from html.parser import HTMLParser

from tests.setup_support import local_browser
from tests.test_personal_login import owner


class LoginInputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs = {}
        self.labels = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") in {"access_key", "passcode"}:
            self.inputs[attrs["name"]] = attrs
        if tag == "label":
            self.labels.add(attrs.get("for"))


def test_login_fields_remain_native_editable_and_explicitly_labeled(client, monkeypatch):
    with local_browser() as browser:
        owner(browser, monkeypatch)
        browser.cookies.clear()
        response = browser.get("/login")
        assert response.status_code == 200
        inputs = LoginInputs(response.text)
        for name, kind, autocomplete in (
            ("access_key", "text", "username"),
            ("passcode", "password", "current-password"),
        ):
            field = inputs.inputs[name]
            assert field["type"] == kind and field["autocomplete"] == autocomplete
            assert field["inputmode"] == "text" and field["id"] in inputs.labels
            assert not {"readonly", "disabled", "autofocus"}.intersection(field)
            assert "value" not in field


def test_switch_fields_use_the_same_native_contract_and_keep_authentication(client, monkeypatch):
    with local_browser() as browser:
        owner(browser, monkeypatch)
        response = browser.get("/ui/switch-person")
        assert response.status_code == 200
        assert 'action="/ui/switch-person"' in response.text
        assert len(LoginInputs(response.text).inputs) == 2
        blocked = browser.post(
            "/ui/switch-person",
            headers={"Origin": "https://example.invalid"},
            data={"access_key": "Invented", "passcode": "invented-only"},
        )
        assert blocked.status_code == 403
        assert browser.get("/ui/movies").status_code == 200
