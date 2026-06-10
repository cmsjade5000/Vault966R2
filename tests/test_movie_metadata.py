from core.movie_metadata import MovieMetadata


def test_movie_metadata_normalizes_legacy_and_enriched_shapes():
    metadata = MovieMetadata.from_mapping(
        {
            "title": "Arrival",
            "release_year": "2016.0",
            "runtime_min": "116.0",
            "plot_summary": "First contact.",
            "certificate": "PG-13",
            "keywords": "language; first contact",
            "genres": "Drama | Sci-Fi; Mystery",
            "digital_location": "iTunes",
            "providers_rent": "Apple TV; Vudu",
            "languages": "English; fr",
            "countries": "United States; CA",
            "franchise": "Arrival Collection",
            "rt_percent": "94",
            "director": "Denis Villeneuve",
            "top_3_actors": "Amy Adams | Jeremy Renner | Forest Whitaker",
        }
    )

    assert metadata.year == 2016
    assert metadata.runtime == 116
    assert metadata.plot == "First contact."
    assert metadata.genres == ["Drama", "Science Fiction", "Mystery"]
    assert metadata.where_to_watch == ["iTunes", "Apple TV (rent)", "Vudu (rent)"]
    assert metadata.languages == ["en", "fr"]
    assert metadata.countries == ["US", "CA"]
    assert metadata.collection == "Arrival Collection"
    assert metadata.rt_score == 94
    assert metadata.directors == ["Denis Villeneuve"]
    assert metadata.cast == ["Amy Adams", "Jeremy Renner", "Forest Whitaker"]
    assert metadata.certificate == "PG-13"
    assert metadata.keywords == ["language", "first contact"]


def test_movie_metadata_payload_hash_is_stable_for_same_content():
    first = MovieMetadata.from_mapping(
        {"title": "Heat", "genres": "Drama | Crime", "digital_location": "Vudu"}
    )
    second = MovieMetadata.from_mapping(
        {"title": "Heat", "genres": ["Drama", "Crime"], "where_to_watch": ["Vudu"]}
    )

    assert first.payload_sha() == second.payload_sha()
