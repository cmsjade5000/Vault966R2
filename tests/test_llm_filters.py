import pytest
from pydantic import ValidationError

from api.schemas.llm_filters import LlmMovieFilters
from api.services.llm_filters import normalize_llm_filters


def test_llm_filters_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LlmMovieFilters.model_validate(
            {
                "q": "robots",
                "genres": ["Sci-Fi"],
                "moods": [],
                "order_by": "title_asc",
                "sql": "select * from movies",
            }
        )


def test_llm_filters_rejects_invalid_ranges() -> None:
    with pytest.raises(ValidationError):
        LlmMovieFilters.model_validate(
            {
                "genres": [],
                "moods": [],
                "order_by": "title_asc",
                "year_min": 2000,
                "year_max": 1990,
            }
        )


def test_normalize_llm_filters_maps_allowed_labels() -> None:
    filters = LlmMovieFilters.model_validate(
        {
            "genres": ["Sci-Fi", "Drama", "Unknown"],
            "moods": ["Moody", "Cozy"],
            "order_by": "title_asc",
        }
    )
    normalized = normalize_llm_filters(
        filters,
        allowed_genres=["Science Fiction", "Drama"],
        allowed_moods=["Moody"],
    )
    assert normalized.genres == ["Science Fiction", "Drama"]
    assert normalized.moods == ["Moody"]
