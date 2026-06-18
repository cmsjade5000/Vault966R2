from core.display_titles import display_movie_title


def test_display_movie_title_hides_trailing_year_and_edition_labels() -> None:
    assert display_movie_title("The Addams Family (2019)") == "The Addams Family"
    assert display_movie_title("Alien (1979) (Director's Cut)") == "Alien"
    assert display_movie_title("American Pie (Unrated Extended Edition)") == "American Pie"
    assert display_movie_title("Blade Runner - Special Edition") == "Blade Runner"


def test_display_movie_title_preserves_meaningful_parentheticals() -> None:
    assert display_movie_title("(500) Days of Summer") == "(500) Days of Summer"
    assert (
        display_movie_title("Batman v Superman: Dawn of Justice")
        == "Batman v Superman: Dawn of Justice"
    )
    assert display_movie_title("Precious (Based on the Novel Push by Sapphire)") == (
        "Precious (Based on the Novel Push by Sapphire)"
    )
