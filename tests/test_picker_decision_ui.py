"""Synthetic decision-screen regressions independent of login input changes."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit


class DecisionScreen(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.buttons = []
        self.primary = []
        self.details = []
        self.edits = []
        self.resets = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "button" and "data-preference-button" in attrs:
            self.buttons.append(attrs)
        if tag == "a" and "data-match-primary" in attrs:
            self.primary.append(attrs)
        if tag == "details":
            self.details.append(attrs)
        if tag == "a" and "data-match-edit" in attrs:
            self.edits.append(attrs)
        if tag == "a" and "data-match-reset" in attrs:
            self.resets.append(attrs)


def test_decision_has_one_primary_action_and_preserves_state_in_detail_links(client):
    response = client.get("/ui/match", params={"show": 1})
    assert response.status_code == 200
    screen = DecisionScreen(response.text)
    assert len(screen.primary) == 1 and len(screen.resets) == 1
    assert "button-primary" in screen.primary[0]["class"]
    detail = urlsplit(screen.primary[0]["href"])
    assert detail.path.startswith("/ui/movies/")
    assert parse_qs(detail.query)["return_to"] == ["/ui/match?show=1"]
    assert 'class="match-progress"' not in response.text
    assert "Your picks for tonight" in response.text
    for name in ("match-fit-details", "match-preferences"):
        disclosure = next(item for item in screen.details if item.get("class") == name)
        assert "open" not in disclosure
    assert [parse_qs(urlsplit(item["href"]).query)["edit"] for item in screen.edits] == [
        [str(index)] for index in range(5)
    ]


def test_picker_uses_shared_preference_contract_and_heart_before_watchlist(client):
    response = client.get("/ui/match", params={"show": 1})
    screen = DecisionScreen(response.text)
    assert len(screen.buttons) >= 2 and len(screen.buttons) % 2 == 0
    for like, watchlist in zip(screen.buttons[::2], screen.buttons[1::2]):
        assert [like["data-preference-type"], watchlist["data-preference-type"]] == [
            "like",
            "watchlist",
        ]
        assert like["data-movie-id"] == watchlist["data-movie-id"]
        for button in (like, watchlist):
            assert "preference-icon" in button["class"]
            assert button["type"] == "button"
            assert button["aria-label"] and button["aria-pressed"] in {"true", "false"}
    assert "discover-action" not in response.text


def test_question_flow_retains_progress_and_widened_results_keep_the_notice(client):
    question = client.get("/ui/match", params={"answers": "funny,high"})
    assert 'class="match-progress"' in question.text
    assert "Show picks now" in question.text and "Question 3" in question.text
    widened = client.get("/ui/match", params={"answers": "intense,high,long,family,recent"})
    assert widened.status_code == 200
    assert 'class="match-notice"' in widened.text
    assert "View these filters in Library" in widened.text
