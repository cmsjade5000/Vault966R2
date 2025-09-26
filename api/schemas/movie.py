from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from api.models.person import RoleType
from api.schemas.person import PersonRead


class GenreRead(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class MoodRead(BaseModel):
    id: int
    name: str
    emoji: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class MovieBase(BaseModel):
    title: str
    year: Optional[int] = None
    runtime: Optional[int] = None
    plot: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    where_to_watch: Optional[str] = None
    languages: Optional[str] = None
    countries: Optional[str] = None
    collection: Optional[str] = None


class MovieCreate(MovieBase):
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)


class MovieRead(MovieBase):
    id: int
    genres: List[GenreRead] = Field(default_factory=list)
    moods: List[MoodRead] = Field(default_factory=list)
    flagged: bool = False

    class Config:
        from_attributes = True


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = None
    runtime: Optional[int] = None
    plot: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    where_to_watch: Optional[List[str]] = None
    genres: Optional[List[str]] = None
    resolve_flag: bool = False


class MovieFacets(BaseModel):
    genres: Dict[str, int] = Field(default_factory=dict)
    moods: Dict[str, int] = Field(default_factory=dict)


class MovieLookupCandidate(BaseModel):
    title: str
    year: Optional[int] = None
    runtime: Optional[int] = None
    synopsis: str = ""
    overview: str = ""
    tmdb_id: int
    imdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    release_date: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    source: str = "tmdb"
    where_to_watch: List[str] = Field(default_factory=list)


class MovieLookupResponse(BaseModel):
    items: List[MovieLookupCandidate] = Field(default_factory=list)


class MovieSearchResponse(BaseModel):
    items: List[MovieRead]
    total: int
    page: int
    page_size: int
    facets: MovieFacets

    class Config:
        from_attributes = True


class MovieFlagCreate(BaseModel):
    reason: Optional[str] = None
    notes: Optional[str] = None


class MovieFlagRead(BaseModel):
    movie_id: int
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleAttach(BaseModel):
    role_type: RoleType
    person_id: int
    character_name: Optional[str] = None
    billing_order: Optional[int] = None


class RoleRead(BaseModel):
    id: int
    movie_id: int
    person_id: int
    role_type: RoleType
    character_name: Optional[str] = None
    billing_order: Optional[int] = None
    person: PersonRead

    class Config:
        from_attributes = True
