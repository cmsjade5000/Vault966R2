from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssistantRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    limit: int = Field(default=6, ge=1, le=12)

    model_config = ConfigDict(extra="forbid")


class AssistantMovie(BaseModel):
    id: int
    title: str
    year: Optional[int] = None
    runtime: Optional[int] = None
    imdb_rating: Optional[float] = None
    rt_score: Optional[int] = None
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)


class AssistantResponse(BaseModel):
    reply: str
    movies: List[AssistantMovie] = Field(default_factory=list)
