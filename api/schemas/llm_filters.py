from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.schemas.movie import MovieFacets, MovieRead


ALLOWED_ORDER_BY = (
    "title_asc",
    "title_desc",
    "year_desc",
    "runtime_asc",
    "imdb_desc",
    "rt_desc",
    "flic",
)


class LlmMovieFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    q: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    runtime_min: Optional[int] = None
    runtime_max: Optional[int] = None
    order_by: str = "title_asc"

    @field_validator("q")
    @classmethod
    def _clean_q(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("genres", "moods")
    @classmethod
    def _drop_empty_labels(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in value:
            label = item.strip()
            if label and label not in cleaned:
                cleaned.append(label)
        return cleaned

    @field_validator("order_by")
    @classmethod
    def _validate_order_by(cls, value: str) -> str:
        if value not in ALLOWED_ORDER_BY:
            raise ValueError("order_by must be a supported sort")
        return value

    @model_validator(mode="after")
    def _validate_ranges(self) -> "LlmMovieFilters":
        if self.year_min is not None and (self.year_min < 1888 or self.year_min > 2100):
            raise ValueError("year_min must be between 1888 and 2100")
        if self.year_max is not None and (self.year_max < 1888 or self.year_max > 2100):
            raise ValueError("year_max must be between 1888 and 2100")
        if (
            self.year_min is not None
            and self.year_max is not None
            and self.year_min > self.year_max
        ):
            raise ValueError("year_min must be less than or equal to year_max")
        if self.runtime_min is not None and self.runtime_min < 0:
            raise ValueError("runtime_min must be non-negative")
        if self.runtime_max is not None and self.runtime_max < 0:
            raise ValueError("runtime_max must be non-negative")
        if (
            self.runtime_min is not None
            and self.runtime_max is not None
            and self.runtime_min > self.runtime_max
        ):
            raise ValueError("runtime_min must be less than or equal to runtime_max")
        return self


class LlmMovieSearchRequest(BaseModel):
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


class LlmMovieSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: LlmMovieFilters
    items: List[MovieRead]
    total: int
    page: int
    page_size: int
    facets: MovieFacets
