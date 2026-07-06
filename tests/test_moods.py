from core.moods import (
    MOOD_TAXONOMY,
    analyze_moods,
    avoidance_flags_for_moods,
    normalize_mood_labels,
    score_moods,
)


def test_score_moods_uses_controlled_taxonomy() -> None:
    moods = score_moods(
        ["Horror", "Mystery"],
        keywords=["haunted house"],
        plot="A family moves into a haunted home with a dark secret.",
    )

    assert moods[:2] == ["Scary", "Atmospheric"]
    assert set(moods).issubset(MOOD_TAXONOMY)


def test_mood_analysis_is_explainable() -> None:
    analysis = analyze_moods(
        ["Comedy", "Romance"],
        keywords=["romantic comedy", "wedding"],
        plot="Two old friends fall in love before a wedding.",
    )

    romantic = next(item for item in analysis.selected if item.mood == "Romantic")
    assert romantic.score >= 4
    assert "keyword:romantic comedy" in romantic.explanation
    assert "plot:fall in love" in romantic.explanation


def test_score_moods_is_conservative_with_plot_only_signal() -> None:
    assert score_moods([], plot="A strange truth about the past is revealed.") == []


def test_score_moods_limits_and_orders_deterministically() -> None:
    moods = score_moods(
        ["Action", "Adventure", "War", "Science Fiction"],
        keywords=["quest", "battle", "space opera", "time travel"],
        runtime=142,
        max_moods=3,
    )

    assert moods == ["Epic", "High-energy", "Mind-bending"]


def test_normalize_mood_labels_maps_legacy_aliases() -> None:
    assert normalize_mood_labels([" Moody ", "Exciting", "Dark", "Moody"]) == (
        "Atmospheric",
        "High-energy",
        "Bleak",
    )


def test_avoidance_flags_are_derived_from_positive_moods_and_runtime() -> None:
    flags = avoidance_flags_for_moods(["Scary", "Bleak", "Epic"], runtime=151)

    assert "not_scary" in flags
    assert "not_bleak" in flags
    assert "not_long" in flags
