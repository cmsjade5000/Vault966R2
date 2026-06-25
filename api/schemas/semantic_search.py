from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.movie import MovieFacets, MovieRead


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    year_min: Optional[int] = Field(default=None, ge=1800, le=2100)
    year_max: Optional[int] = Field(default=None, ge=1800, le=2100)
    runtime_min: Optional[int] = Field(default=None, ge=1, le=600)
    runtime_max: Optional[int] = Field(default=None, ge=1, le=600)
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=24, ge=1, le=100)


class SemanticSearchItem(MovieRead):
    similarity_score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(from_attributes=True)


class SemanticSearchResponse(BaseModel):
    items: List[SemanticSearchItem]
    total: int
    page: int
    page_size: int
    facets: MovieFacets
    mode: str
    notice: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
