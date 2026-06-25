from core.poster_theme import select_poster_theme


def test_poster_theme_handles_war_drama_combo() -> None:
    theme = select_poster_theme(["War; Drama"])
    assert theme == "poster-theme-war"


def test_poster_theme_handles_science_fiction_combo() -> None:
    theme = select_poster_theme(["Sci-Fi / Science Fiction"])
    assert theme == "poster-theme-sci-fi"
