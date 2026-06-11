from scripts.backfill_clear_external_matches import exact_title_year, release_year


def test_release_year_accepts_omdb_ranges() -> None:
    assert release_year("2019") == 2019
    assert release_year("2019–2020") == 2019
    assert release_year("") is None


def test_exact_title_year_requires_both_fields() -> None:
    assert exact_title_year("The Addams Family (2019)", 2019, "The Addams Family", "2019")
    assert exact_title_year("Her (2013)", 2013, "Her", "2013-12-18")
    assert not exact_title_year("Footloose", 1984, "Footloose", "2011-10-14")
    assert not exact_title_year("The Gift", 2015, "The Gifted", "2015")
