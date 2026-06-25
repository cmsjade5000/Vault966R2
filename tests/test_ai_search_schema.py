import pytest
from pydantic import ValidationError

from api.schemas.ai_search import AiSearchRequest, SearchPlan


def test_ai_search_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        AiSearchRequest.model_validate({"query": "   "})


def test_search_plan_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SearchPlan.model_validate(
            {
                "q": "robots",
                "genres": ["Sci-Fi"],
                "moods": [],
                "order_by": "title_asc",
                "sql": "select * from movies",
            }
        )
