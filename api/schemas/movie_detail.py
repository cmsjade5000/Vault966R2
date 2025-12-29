from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)


class SimilarMovie(BaseModel):
    id: int
    title: str
    poster_url: Optional[str] = None
    year: Optional[int] = None
    flic_score: Optional[float] = None
    poster_theme: Optional[str] = None


class TopBilledEntry(BaseModel):
    name: str
    character: Optional[str] = None
    imdb_id: Optional[str] = None
    person_id: Optional[int] = None


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
    metascore: Optional[int] = None
    tomato_meter: Optional[int] = None
    tomato_audience: Optional[int] = None
    rt_score: Optional[int] = None
    awards: Optional[str] = None
    where_to_watch: List[str] = Field(default_factory=list)
    languages: Optional[Union[str, List[str]]] = None
    countries: Optional[Union[str, List[str]]] = None
    languages_iso: List[str] = Field(default_factory=list)
    countries_iso: List[str] = Field(default_factory=list)
    languages_display: List[str] = Field(default_factory=list)
    countries_display: List[str] = Field(default_factory=list)
    collection: Optional[str] = None
    last_tmdb_fetch_at: Optional[datetime] = None
    last_omdb_fetch_at: Optional[datetime] = None
    tmdb_etag: Optional[str] = None
    tmdb_payload_sha: Optional[str] = None
    omdb_payload_sha: Optional[str] = None
    roles: List[RoleWithPersonRead] = Field(default_factory=list)
    similar: List[SimilarMovie] = Field(default_factory=list)
    poster_theme: Optional[str] = None
    flagged: bool = False
    top_billed: List[TopBilledEntry] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
