from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.movie_flag import MovieFlag
from api.services.movie_match import (
    build_match_result,
    build_preferences,
    normalize_answer_ids,
)


MATCH_ANSWERS = "funny,short,older,light,keep"


def test_match_preferences_compile_answers_to_constraints() -> None:
    preferences = build_preferences(("funny", "short", "older", "light", "keep"))

    assert preferences.runtime_max == 100
    assert preferences.year_max == 1999
    assert "Comedy" in preferences.genres
    assert "Animation" in preferences.genres
    assert "Family" in preferences.moods


def test_match_normalizes_only_valid_question_sequence() -> None:
    assert normalize_answer_ids("funny,short,older") == ("funny", "short", "older")
    assert normalize_answer_ids("short,funny") == ()
    assert normalize_answer_ids("funny,sideways,older") == ("funny",)


def test_match_result_returns_lead_and_shortlist(db_session) -> None:
    result = build_match_result(db_session, answer_ids=MATCH_ANSWERS)

    assert result.complete is True
    assert result.current_question is None
    assert result.lead is not None
    assert result.lead.movie.title == "Toy Story"
    assert len(result.supporting) <= 6
    assert "Keeps it tight" in result.lead.reasons


def test_match_result_excludes_flagged_movies(db_session) -> None:
    toy_story = db_session.query(Movie).filter(Movie.title == "Toy Story").one()
    db_session.add(MovieFlag(movie_id=toy_story.id, reason="Verify identity"))
    db_session.commit()

    result = build_match_result(db_session, answer_ids=MATCH_ANSWERS)
    titles = [match.movie.title for match in ((result.lead,) if result.lead else ()) + result.supporting]

    assert "Toy Story" not in titles


def test_match_result_widens_when_no_title_hits_every_answer(db_session) -> None:
    result = build_match_result(
        db_session,
        answer_ids="scary,long,newer,light,keep",
    )

    assert result.complete is True
    assert result.widened is True
    assert result.lead is not None


def test_match_page_renders_first_question_and_active_nav(client: TestClient) -> None:
    response = client.get("/ui/match")

    assert response.status_code == 200
    html = response.text
    assert "Narrow It Down" in html
    assert 'href="/ui/match"' in html
    assert 'aria-current="page"' in html
    assert "Scary" in html
    assert "Funny" in html
    assert "Flic" not in html


def test_match_page_renders_result_shortlist(client: TestClient) -> None:
    response = client.get("/ui/match", params={"answers": MATCH_ANSWERS})

    assert response.status_code == 200
    html = response.text
    assert "Top Match" in html
    assert "Toy Story" in html
    assert "Also in the Mix" in html
    assert "Try another" in html
    assert "Flic" not in html
