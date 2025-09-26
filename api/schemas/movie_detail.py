from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PersonNested(BaseModel):
    id: int
    name: str
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None


class RoleWithPersonRead(BaseModel):
    id: int
    movie_id: int
    person_id: int
    role_type: str
    character_name: Optional[str] = None
    billing_order: Optional[int] = None
    person: PersonNested

    class Config:
        from_attributes = True


class SimilarMovie(BaseModel):
    id: int
    title: str
    poster_url: Optional[str] = None
    year: Optional[int] = None
    flic_score: Optional[float] = None
    poster_theme: Optional[str] = None


class MovieDetail(BaseModel):
    id: int
    title: str
    year: Optional[int] = None
    runtime: Optional[int] = None
    plot: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    rt_score: Optional[int] = None
    where_to_watch: List[str] = Field(default_factory=list)
    languages: Optional[str] = None
    countries: Optional[str] = None
    collection: Optional[str] = None
    roles: List[RoleWithPersonRead] = Field(default_factory=list)
    similar: List[SimilarMovie] = Field(default_factory=list)
    poster_theme: Optional[str] = None
    flagged: bool = False

    class Config:
        from_attributes = True
