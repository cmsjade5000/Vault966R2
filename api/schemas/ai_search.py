from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.schemas.llm_filters import LlmMovieFilters
from api.schemas.movie import MovieFacets, MovieRead


class SearchPlan(LlmMovieFilters):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class AiSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    query: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=24, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be empty")
        return cleaned


class AiSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: SearchPlan
    explanation: str
    items: List[MovieRead]
    total: int
    page: int
    page_size: int
    facets: MovieFacets
