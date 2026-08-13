import httpx
import pytest
from pydantic import ValidationError

from api.config import settings
from api.schemas.llm_filters import LlmMovieFilters
from api.services.llm_filters import LlmFilterError, generate_llm_filters, normalize_llm_filters


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


def test_llm_provider_error_redacts_authorization_secret(monkeypatch) -> None:
    sentinel = "SENTINEL_LLM_AUTH_SECRET"
    monkeypatch.setattr(settings, "llm_api_key", sentinel)

    class FailingClient:
        def post(self, url, *, json, headers):
            request = httpx.Request("POST", url, json=json, headers=headers)
            raise httpx.RequestError(
                f"connection reset; Authorization: Bearer {sentinel}",
                request=request,
            )

    with pytest.raises(LlmFilterError) as error_info:
        generate_llm_filters(
            "moody science fiction",
            allowed_genres=["Science Fiction"],
            allowed_moods=["Moody"],
            client=FailingClient(),
        )

    message = str(error_info.value)
    assert error_info.value.__cause__ is None
    assert sentinel not in message
    assert "Authorization: [REDACTED]" in message
    assert "connection reset" in message
