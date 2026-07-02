import pathlib

import pytest

from core.enriched_csv import normalize_languages, normalize_where_to_watch
from scripts.enriched_csv_review import (
    ENRICHED_CSV_REQUIRED_COLUMNS,
    EnrichedCsvContractError,
    GateConfig,
    apply_overrides,
    normalize_row,
    quality_flags,
    validate_enriched_contract,
)


def test_normalize_where_to_watch_removes_urls_and_splits_buckets():
    value = "Netflix; https://www.themoviedb.org/movie/123/watch?locale=US; Amazon Video (rent); Apple TV (buy)"
    watch = normalize_where_to_watch(value, region="US")
    assert watch.stream == ["Netflix"]
    assert watch.rent == ["Amazon Video"]
    assert watch.buy == ["Apple TV"]
    assert watch.tmdb_watch_url and "themoviedb.org/movie/123" in watch.tmdb_watch_url


def test_normalize_languages_prefers_iso_codes_and_maps_common_names():
    normalized = normalize_languages("English; fr; Mandarin; Klingon")
    assert "en" in normalized.iso
    assert "fr" in normalized.iso
    assert "zh" in normalized.iso
    assert "English" in normalized.display
    assert "Klingon" in normalized.unmapped


def test_apply_overrides_updates_rows(tmp_path: pathlib.Path):
    rows = [
        {
            "title": "Short Film",
            "year": "2020",
            "runtime_min": "12",
            "poster_url": "x",
            "backdrop_url": "y",
        },
    ]
    overrides_path = tmp_path / "needs_review.csv"
    overrides_path.write_text(
        "title,year,reasons,suggested_fix,override_runtime_min\nShort Film,2020,runtime_too_short,fix it,95\n",
        encoding="utf-8",
    )
    applied = apply_overrides(rows, overrides_path)
    assert applied == 1
    assert rows[0]["runtime_min"] == "95"


def _base_enriched_row() -> dict[str, str]:
    return {
        "title": "Solaris",
        "year": "1972",
        "imdb_id": "tt0069293",
        "tmdb_id": "13848",
        "runtime_min": "167",
        "plot": "A psychologist is sent to a station orbiting Solaris.",
        "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w780/backdrop.jpg",
        "genres": "Drama; Sci-Fi",
        "moods": "",
        "keywords": "",
        "imdb_rating": "8.1",
        "imdb_votes": "50000",
        "rt_score": "90",
        "watch_region": "US",
        "providers_stream": "Criterion Channel",
        "providers_rent": "",
        "providers_buy": "",
        "tmdb_watch_url": "https://www.themoviedb.org/movie/13848/watch?locale=US",
        "languages": "en",
        "countries": "US",
        "collection": "",
        "tmdb_last_scraped": "2023-05-01T12:00:00+00:00",
    }


def test_validate_enriched_contract_accepts_valid_row():
    fieldnames = list(ENRICHED_CSV_REQUIRED_COLUMNS)
    rows = [_base_enriched_row()]
    validate_enriched_contract(fieldnames, rows)


def test_validate_enriched_contract_rejects_missing_required_columns():
    fieldnames = ["title", "year"]
    with pytest.raises(EnrichedCsvContractError):
        validate_enriched_contract(fieldnames, [])


def test_validate_enriched_contract_rejects_malformed_values():
    fieldnames = list(ENRICHED_CSV_REQUIRED_COLUMNS)
    row = _base_enriched_row()
    row["year"] = "19x7"
    with pytest.raises(EnrichedCsvContractError):
        validate_enriched_contract(fieldnames, [row])


def test_validate_enriched_contract_rejects_fractional_integer_fields():
    fieldnames = list(ENRICHED_CSV_REQUIRED_COLUMNS)
    row = _base_enriched_row()
    row["runtime_min"] = "90.5"

    with pytest.raises(EnrichedCsvContractError, match="runtime_min is not an integer"):
        validate_enriched_contract(fieldnames, [row])


def test_validate_enriched_contract_accepts_integer_like_decimal_fields():
    fieldnames = list(ENRICHED_CSV_REQUIRED_COLUMNS)
    row = _base_enriched_row()
    row["runtime_min"] = "90.0"

    validate_enriched_contract(fieldnames, [row])


def test_quality_flags_are_deterministic():
    row = {
        "title": "Test",
        "year": "2020",
        "runtime_min": "10",
        "poster_url": "",
        "backdrop_url": "",
        "tmdb_last_scraped": "",
        "imdb_votes": "10",
        "imdb_rating": "8.0",
        "languages": "Klingon",
        "countries": "Wakanda",
    }
    flags = quality_flags(row, GateConfig(min_runtime=40, min_mainstream_votes=2000))
    assert flags == [
        "runtime_too_short",
        "missing_poster",
        "missing_backdrop",
        "missing_tmdb_last_scraped",
        "imdb_votes_implausibly_low",
        "languages_unmapped",
        "countries_unmapped",
    ]


def test_normalize_row_preserves_structured_watch_url_without_provider_names():
    row = _base_enriched_row()
    row["providers_stream"] = ""
    row["providers_rent"] = ""
    row["providers_buy"] = ""

    normalized = normalize_row(row, GateConfig())

    assert normalized["watch_region"] == "US"
    assert normalized["tmdb_watch_url"] == row["tmdb_watch_url"]
    assert normalized["providers_stream"] == ""


def test_normalize_row_flags_unmapped_languages_before_iso_rewrite():
    row = _base_enriched_row()
    row["languages"] = "English; Klingon"

    normalized = normalize_row(row, GateConfig())

    assert "languages_unmapped" in normalized["quality_flags"]
    assert normalized["quality_quarantined"] == "true"
    assert normalized["languages"] == "en"
