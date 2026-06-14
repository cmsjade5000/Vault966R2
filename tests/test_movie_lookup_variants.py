from api.services.movie_lookup import _clean_title_aliases, iter_tmdb_search_variants


def test_iter_tmdb_search_variants_includes_alias_cleanup_and_year_tolerance():
    variants = iter_tmdb_search_variants("Movie Title [2009] Part I & Friends", 2010)
    # Contains cleaned alias variant (brackets removed, & -> and, roman -> digit)
    cleaned = [q for q, y, tag in variants if tag.startswith("alias_cleaned") and y == 2010]
    assert cleaned
    assert "and" in cleaned[0].lower()
    assert "part 1" in cleaned[0].lower()

    years = {y for _, y, _ in variants}
    assert 2010 in years
    assert 2008 in years
    assert 2012 in years
    assert None in years


def test_clean_title_aliases_removes_year_and_edition_suffixes():
    assert _clean_title_aliases("Cinderella (2015)") == "Cinderella"
    assert _clean_title_aliases("The Boss (Unrated)") == "The Boss"
    assert (
        _clean_title_aliases("The Last House (Unrated) [2009]")
        == "The Last House"
    )
