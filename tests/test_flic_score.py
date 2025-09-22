from core.picker import calculate_flic_score


def test_flic_score_genre_and_mood_bonus():
    candidate = {
        "genres": ["Sci-Fi", "Drama"],
        "moods": ["Moody"],
        "runtime": 105,
        "year": 2012,
    }
    filters = {
        "genres": ["Sci-Fi"],
        "moods": ["Moody"],
        "runtime_max": 120,
        "year_min": 2010,
        "year_max": 2020,
    }
    score, breakdown = calculate_flic_score(candidate, filters)
    assert score > 100
    assert breakdown["genre_match"] == 20
    assert breakdown["mood_match"] == 15
    assert breakdown["runtime_match"] == 10
    assert breakdown["year_bonus"] == 10


def test_flic_score_penalties():
    candidate = {
        "genres": ["Comedy"],
        "moods": [],
        "runtime": 150,
        "year": 1990,
    }
    filters = {
        "genres": ["Sci-Fi"],
        "moods": ["Moody"],
        "runtime_max": 120,
        "year_min": 2000,
        "year_max": 2010,
    }
    score, breakdown = calculate_flic_score(candidate, filters)
    assert score < 100
    assert breakdown["genre_miss"] == -5
    assert breakdown["mood_miss"] == -5
    assert breakdown["runtime_over"] < 0
    assert breakdown["year_penalty"] < 0
