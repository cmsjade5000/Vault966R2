import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from api.models.movie import Genre, Mood, Movie
from api.models.movie_flag import MovieFlag
from api.services import movie_match as movie_match_service
from api.services.movie_match import (
    QUESTIONS,
    build_match_result,
    build_preferences,
    complete_answer_ids,
    normalize_answer_ids,
)

MATCH_ANSWERS = "cozy,low,short,family,retro"


def test_match_preferences_compile_answers_to_constraints() -> None:
    preferences = build_preferences(("cozy", "low", "short", "family", "retro"))

    assert preferences.answer_ids == ("cozy", "low", "short", "family", "retro")
    assert preferences.runtime_max == 99
    assert preferences.year_min == 1980
    assert preferences.year_max == 1999
    assert "Animation" in preferences.genres
    assert "Family" in preferences.moods
    assert "Light" in preferences.moods
    assert preferences.energy == "low"
    assert preferences.genre_label == "Animation & family"


def test_match_infers_moods_lazily_and_at_most_once_per_movie(db_session, monkeypatch) -> None:
    calls = 0
    original_score_moods = movie_match_service.score_moods

    def counted_score_moods(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_score_moods(*args, **kwargs)

    monkeypatch.setattr(movie_match_service, "score_moods", counted_score_moods)
    trusted_count = db_session.query(Movie).count()

    build_match_result(db_session, answer_ids="cozy")
    assert calls == 0

    build_match_result(db_session, answer_ids="any_mood")
    assert calls == 0

    build_match_result(db_session, answer_ids=MATCH_ANSWERS)

    assert calls <= trusted_count


def test_match_questions_cover_each_requested_dimension_once() -> None:
    assert [question.id for question in QUESTIONS] == [
        "mood",
        "energy",
        "runtime",
        "genre",
        "era",
    ]
    option_ids = [option.id for question in QUESTIONS for option in question.options]
    assert len(option_ids) == len(set(option_ids))


def test_match_normalizes_only_valid_question_sequence() -> None:
    assert normalize_answer_ids("funny,high,standard") == ("funny", "high", "standard")
    assert normalize_answer_ids("short,funny") == ()
    assert normalize_answer_ids("funny,sideways,retro") == ("funny",)


def test_match_can_complete_with_explicit_skips() -> None:
    assert complete_answer_ids(("funny", "any_energy")) == (
        "funny",
        "any_energy",
        "any_runtime",
        "any_genre",
        "any_era",
    )


def test_match_result_returns_lead_and_shortlist(db_session) -> None:
    result = build_match_result(db_session, answer_ids=MATCH_ANSWERS)

    assert result.complete is True
    assert result.current_question is None
    assert result.trusted_pool_count > 0
    assert result.reroll_pool_size > 0
    assert result.result_quality in {"exact", "softened", "widened"}
    assert result.lead is not None
    assert result.lead.movie.title == "Toy Story"
    assert len(result.supporting) == 4
    assert result.lead.why_it_fits
    assert "81-minute runtime" in result.lead.reasons
    assert "genres=Animation" in result.library_filter_query
    assert len({match.movie.id for match in (result.lead, *result.supporting)}) == 5


def test_match_result_excludes_flagged_movies(db_session) -> None:
    toy_story = db_session.query(Movie).filter(Movie.title == "Toy Story").one()
    db_session.add(MovieFlag(movie_id=toy_story.id, reason="Verify identity"))
    db_session.commit()

    result = build_match_result(db_session, answer_ids=MATCH_ANSWERS)
    titles = [
        match.movie.title for match in ((result.lead,) if result.lead else ()) + result.supporting
    ]

    assert "Toy Story" not in titles


def test_match_result_widens_when_no_title_hits_every_answer(db_session) -> None:
    result = build_match_result(
        db_session,
        answer_ids="intense,high,long,family,recent",
    )

    assert result.complete is True
    assert result.widened is True
    assert result.fallback_tier in {"relaxed_mood", "relaxed_lane", "catalog"}
    assert result.fallback_notice
    assert result.lead is not None


def test_match_state_counts_options_and_answer_trail(db_session) -> None:
    result = build_match_result(db_session, answer_ids="funny,high")

    assert result.complete is False
    assert result.candidate_count <= result.trusted_pool_count
    assert [step.label for step in result.step_states] == ["Funny", "High-energy"]
    assert all(step.after_count <= step.before_count for step in result.step_states)
    assert {state.option.id for state in result.option_states} == {
        "short",
        "standard",
        "long",
        "any_runtime",
    }
    assert all(state.after_count <= state.before_count for state in result.option_states)


def test_match_mood_and_energy_are_ranking_signals(db_session) -> None:
    result = build_match_result(db_session, answer_ids="thoughtful,high")

    assert result.complete is False
    assert result.candidate_count == result.trusted_pool_count
    assert all(state.after_count == state.before_count for state in result.step_states)


def test_match_page_renders_first_question_and_active_nav(client: TestClient) -> None:
    response = client.get("/ui/match")

    assert response.status_code == 200
    html = response.text
    assert "Set the tone. Skip the scroll." in html
    assert 'href="/ui/match"' in html
    assert 'aria-current="page"' in html
    assert "Movie Night Picker" in html
    assert "Cozy" in html
    assert "Funny" in html
    assert "Any mood" in html
    assert "Show picks now" in html
    assert "Flic" not in html


def test_match_page_renders_option_counts_and_trail(client: TestClient) -> None:
    response = client.get("/ui/match", params={"answers": "funny,high"})

    assert response.status_code == 200
    html = response.text
    assert "trusted titles" in html
    assert "Your night" in html
    assert "Funny" in html
    assert "High-energy" in html
    assert "Under 100 minutes" in html
    assert "left" in html


def test_match_page_renders_result_shortlist(client: TestClient, db_session) -> None:
    for movie in db_session.query(Movie).all():
        movie.poster_url = f"https://example.test/posters/{movie.id}.jpg"
    db_session.commit()

    response = client.get("/ui/match", params={"answers": MATCH_ANSWERS})

    assert response.status_code == 200
    html = response.text
    assert "Top Pick" in html
    assert "Toy Story" in html
    assert "More picks for this night" in html
    assert "Try another" not in html
    assert "There isn't another eligible pick in this pool." in html
    assert "View these filters in Library" in html
    assert "Why it fits:" in html
    assert "Quality:" not in html
    assert "Flic" not in html
    detail_href = re.search(r'href="(/ui/movies/\d+\?return_to=[^"]+)"', html)
    assert detail_href is not None
    return_to = parse_qs(urlsplit(unescape(detail_href.group(1))).query)["return_to"][0]
    return_url = urlsplit(return_to)
    assert return_url.path == "/ui/match"
    assert parse_qs(return_url.query) == {"answers": [MATCH_ANSWERS]}
    assert "data-poster-frame" in html
    assert "data-poster-image" in html
    assert "data-poster-fallback hidden" in html


def test_match_page_show_picks_now_keeps_selected_constraints(client: TestClient) -> None:
    response = client.get("/ui/match", params={"answers": "funny,any_energy", "show": 1})

    assert response.status_code == 200
    assert 'class="match-results"' in response.text
    assert "Funny" in response.text
    assert "Any energy" in response.text
    assert "Question 3" not in response.text


def test_partial_runtime_and_genre_answers_keep_hard_constraints(db_session) -> None:
    result = build_match_result(
        db_session,
        answer_ids="any_mood,any_energy,short,family",
    )

    assert result.complete is False
    assert result.current_question is not None
    assert result.current_question.id == "era"
    # The fixture has one title satisfying both explicit hard constraints.
    assert result.candidate_count == 1


def test_show_picks_now_with_no_preferences_renders_a_lead(client: TestClient) -> None:
    response = client.get("/ui/match", params={"show": 1})

    assert response.status_code == 200
    assert 'class="match-results"' in response.text
    assert "Top Pick" in response.text
    assert "No trusted match yet" not in response.text


def test_edit_links_preserve_answers_before_the_edited_step(client: TestClient) -> None:
    response = client.get(
        "/ui/match",
        params={"answers": "funny,high,short,family,retro"},
    )

    assert response.status_code == 200
    assert (
        'href="/ui/match?answers=funny%2Chigh%2Cshort%2Cfamily%2Cretro&amp;edit=2"' in response.text
    )


def test_editing_runtime_preserves_genre_and_era_in_results(client: TestClient) -> None:
    edit_response = client.get(
        "/ui/match",
        params={"answers": "funny,high,short,family,retro", "edit": 2},
    )

    assert edit_response.status_code == 200
    assert "Question 3" in edit_response.text
    assert "100–130 minutes" in edit_response.text
    assert 'href="/ui/match?answers=funny%2Chigh%2Cstandard%2Cfamily%2Cretro"' in edit_response.text

    result_response = client.get(
        "/ui/match",
        params={"answers": "funny,high,standard,family,retro"},
    )

    assert result_response.status_code == 200
    assert "Top Pick" in result_response.text
    assert "100–130 minutes" in result_response.text
    assert "Animation &amp; family" in result_response.text
    assert "1980s &amp; 1990s" in result_response.text


def test_skipped_dimensions_have_distinct_labels_and_no_spurious_fit_reason(
    client: TestClient, db_session
) -> None:
    result = build_match_result(
        db_session,
        answer_ids="any_mood,any_energy,any_runtime,any_genre,any_era",
    )

    assert result.lead is not None
    assert all("Any" not in reason for reason in result.lead.reasons)

    response = client.get("/ui/match", params={"show": 1})
    assert response.status_code == 200
    for label in ("Any mood", "Any energy", "Any runtime", "Any genre", "Any era"):
        assert label in response.text
    assert "Any / skip" not in response.text


def test_reason_does_not_claim_curated_mood_for_inferred_only_candidate(db_session) -> None:
    inferred_only = Movie(
        title="Synthetic Holiday Thriller",
        year=2001,
        runtime=95,
        imdb_id="ttsyntheticmood01",
        tmdb_id=9001,
        plot="A holiday gathering turns into an uneasy night.",
    )
    db_session.add(inferred_only)
    db_session.commit()

    result = build_match_result(
        db_session,
        answer_ids="cozy,low,short,any_genre,any_era",
    )
    match = next(
        match
        for match in ((result.lead,) if result.lead else ()) + result.supporting
        if match.movie.title == inferred_only.title
    )

    assert "Cozy mood" not in match.reasons
    assert any(reason.endswith("-minute runtime") for reason in match.reasons)


def _seed_reroll_movies(db_session) -> list[Movie]:
    """Replace the synthetic fixture with distinct fit and quality scores."""

    for movie in db_session.query(Movie).all():
        db_session.delete(movie)
    db_session.flush()
    animation = db_session.query(Genre).filter(Genre.name == "Animation").one()
    cozy = Mood(name="Cozy")
    intense = Mood(name="Intense")
    movies = [
        Movie(
            title=f"Synthetic Pick {index}",
            vault_id=f"synthetic-{index}",
            year=1990 + index,
            runtime=80 + index,
            imdb_id=f"ttsyntheticpick{index}",
            tmdb_id=9200 + index,
            imdb_rating=9.0 - index,
            genres=[animation],
            moods=[cozy if index == 0 else intense],
        )
        for index in range(6)
    ]
    db_session.add_all(movies)
    db_session.commit()
    return movies


def _reroll_href(html: str) -> str:
    href = re.search(r'href="([^"]+)" data-match-reroll', html)
    assert href is not None
    return unescape(href.group(1))


def test_reroll_cycles_strong_candidates_with_unequal_fit_and_quality(db_session) -> None:
    movies = _seed_reroll_movies(db_session)
    preferences = build_preferences(normalize_answer_ids(MATCH_ANSWERS))
    original_ranking = movie_match_service._rank_movies(movies, preferences, reroll=0)
    expected_ids = [match.movie.id for match in original_ranking[:5]]
    assert len({movie_match_service._score_movie(movie, preferences) for movie in movies}) > 1
    assert len({movie_match_service._quality_score(movie) for movie in movies}) > 1

    for reroll in range(12):
        result = build_match_result(db_session, answer_ids=MATCH_ANSWERS, reroll=reroll)
        assert result.lead is not None
        assert result.lead.movie.id == expected_ids[reroll % len(expected_ids)]
        assert result.reroll_pool_size == 5
        assert result.fallback_tier == "exact"
        assert result.widened is False
        assert {match.movie.id for match in (result.lead, *result.supporting)} == set(expected_ids)


def test_reroll_never_promotes_widened_extras_over_single_exact_match(db_session) -> None:
    for reroll in (0, 1, 2, 49, 50, 101):
        result = build_match_result(db_session, answer_ids=MATCH_ANSWERS, reroll=reroll)
        assert result.lead is not None
        assert result.lead.movie.title == "Toy Story"
        assert result.reroll_pool_size == 1
        assert result.fallback_tier == "exact"
        assert result.widened is True
        assert len(result.supporting) == 4


def test_reroll_keeps_trust_and_hard_constraints(db_session) -> None:
    movies = _seed_reroll_movies(db_session)
    db_session.add(MovieFlag(movie_id=movies[0].id, reason="Synthetic review"))
    movies[1].runtime = 150
    movies[2].year = 2020
    movies[3].genres = [db_session.query(Genre).filter(Genre.name == "Action").one()]
    db_session.commit()
    expected_ids = {movies[4].id, movies[5].id}
    for reroll in range(5):
        result = build_match_result(db_session, answer_ids=MATCH_ANSWERS, reroll=reroll)
        assert result.lead is not None
        assert result.lead.movie.id in expected_ids
        assert result.reroll_pool_size == 2
        assert result.fallback_tier == "exact"
        assert movies[0].id not in {match.movie.id for match in (result.lead, *result.supporting)}


def test_reroll_preserves_existing_fallback_pool(db_session) -> None:
    results = [
        build_match_result(db_session, answer_ids="intense,high,long,family,recent", reroll=index)
        for index in range(6)
    ]
    first = results[0]
    assert first.lead is not None
    expected_ids = [match.movie.id for match in (first.lead, *first.supporting)]
    for index, result in enumerate(results):
        assert result.lead is not None
        assert result.lead.movie.id == expected_ids[index % len(expected_ids)]
        assert result.fallback_tier == first.fallback_tier
        assert result.fallback_notice == first.fallback_notice
        assert result.widened is True


def test_reroll_empty_pool_is_safe_and_renders_empty_state(client, db_session) -> None:
    for movie in db_session.query(Movie).all():
        db_session.add(MovieFlag(movie_id=movie.id, reason="Synthetic review"))
    db_session.commit()
    result = build_match_result(db_session, answer_ids=MATCH_ANSWERS, reroll=50)
    assert result.lead is None
    assert result.supporting == ()
    assert result.reroll_pool_size == 0

    response = client.get("/ui/match", params={"answers": MATCH_ANSWERS, "reroll": 50})
    assert response.status_code == 200
    assert "No trusted match yet" in response.text
    assert "data-match-reroll" not in response.text


def test_reroll_link_wraps_at_route_boundary_and_on_repeated_clicks(client, db_session) -> None:
    _seed_reroll_movies(db_session)
    response = client.get("/ui/match", params={"answers": MATCH_ANSWERS, "reroll": 50})
    assert response.status_code == 200
    assert parse_qs(urlsplit(_reroll_href(response.text)).query) == {
        "answers": [MATCH_ANSWERS],
        "reroll": ["1"],
    }
    leading_titles = []
    for _ in range(12):
        response = client.get(_reroll_href(response.text))
        assert response.status_code == 200
        lead = re.search(r"<h2>(Synthetic Pick \d+)</h2>", response.text)
        assert lead is not None
        leading_titles.append(lead.group(1))
        assert int(parse_qs(urlsplit(_reroll_href(response.text)).query)["reroll"][0]) < 5
    assert len(set(leading_titles[:5])) == 5
    assert leading_titles[:5] == leading_titles[5:10]


def test_show_now_reroll_keeps_completed_answers_and_editing_resets_cycle(client, db_session):
    _seed_reroll_movies(db_session)
    response = client.get(
        "/ui/match", params={"answers": "cozy,low,short,family", "show": 1, "reroll": 50}
    )
    assert response.status_code == 200
    query = parse_qs(urlsplit(_reroll_href(response.text)).query)
    assert query["answers"] == ["cozy,low,short,family,any_era"]
    rerolled = client.get(_reroll_href(response.text))
    assert rerolled.status_code == 200
    assert "Another strong pick" in rerolled.text

    edited = client.get(
        "/ui/match",
        params={"answers": query["answers"][0], "reroll": 50, "edit": 2},
    )
    assert edited.status_code == 200
    assert "Question 3" in edited.text
    assert "data-match-reroll" not in edited.text
    answer_href = re.search(r'href="([^"]+)"\s+data-match-answer', edited.text)
    assert answer_href is not None
    answer_query = parse_qs(urlsplit(unescape(answer_href.group(1))).query)
    assert answer_query == {"answers": [query["answers"][0]]}
    updated = client.get(unescape(answer_href.group(1)))
    assert updated.status_code == 200
    assert "Top Pick" in updated.text
