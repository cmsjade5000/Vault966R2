from datetime import datetime
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer

from api.models.person import RoleType
from api.schemas.person import PersonRead
from api.utils.providers import split_providers
from core.enriched_csv import (
    countries_display_from_iso,
    languages_display_from_iso,
    normalize_countries,
    normalize_languages,
)


class GenreRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class MoodRead(BaseModel):
    id: int
    name: str
    emoji: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MovieBase(BaseModel):
    title: str
    year: Optional[int] = None
    runtime: Optional[int] = None
    plot: Optional[str] = None
    awards: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    metascore: Optional[int] = None
    tomato_meter: Optional[int] = None
    tomato_audience: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    where_to_watch: Optional[Union[str, List[str]]] = None
    languages: Optional[Union[str, List[str]]] = None
    countries: Optional[Union[str, List[str]]] = None
    collection: Optional[str] = None


class MovieCreate(MovieBase):
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)


class MovieRead(MovieBase):
    id: int
    genres: List[GenreRead] = Field(default_factory=list)
    moods: List[MoodRead] = Field(default_factory=list)
    flagged: bool = False
    last_tmdb_fetch_at: Optional[datetime] = None
    last_omdb_fetch_at: Optional[datetime] = None
    tmdb_etag: Optional[str] = None
    tmdb_payload_sha: Optional[str] = None
    omdb_payload_sha: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=List[str])
    def languages_iso(self) -> List[str]:
        value = self.languages
        if value is None:
            return []
        if isinstance(value, list):
            text = "; ".join(str(item) for item in value if item is not None)
        else:
            text = str(value)
        return normalize_languages(text).iso

    @computed_field(return_type=List[str])
    def countries_iso(self) -> List[str]:
        value = self.countries
        if value is None:
            return []
        if isinstance(value, list):
            text = "; ".join(str(item) for item in value if item is not None)
        else:
            text = str(value)
        return normalize_countries(text).iso

    @field_serializer("languages")
    def _serialize_languages(self, value):
        if value is None:
            return None
        if isinstance(value, list):
            codes = normalize_languages(
                "; ".join(str(item) for item in value if item is not None)
            ).iso
            names = languages_display_from_iso(codes) if codes else [str(item) for item in value]
            return ", ".join(names)
        if isinstance(value, str):
            codes = normalize_languages(value).iso
            if not codes:
                return value
            return ", ".join(languages_display_from_iso(codes))
        return str(value)

    @field_serializer("countries")
    def _serialize_countries(self, value):
        if value is None:
            return None
        if isinstance(value, list):
            codes = normalize_countries(
                "; ".join(str(item) for item in value if item is not None)
            ).iso
            names = countries_display_from_iso(codes) if codes else [str(item) for item in value]
            return ", ".join(names)
        if isinstance(value, str):
            codes = normalize_countries(value).iso
            if not codes:
                return value
            return ", ".join(countries_display_from_iso(codes))
        return str(value)

    @computed_field(return_type=List[str])
    def where_to_watch_list(self) -> List[str]:
        return split_providers(self.where_to_watch)


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    year: Optional[int] = None
    runtime: Optional[int] = None
    plot: Optional[str] = None
    awards: Optional[str] = None
    imdb_id: Optional[str] = None
    tmdb_id: Optional[int] = None
    imdb_rating: Optional[float] = None
    imdb_votes: Optional[int] = None
    metascore: Optional[int] = None
    tomato_meter: Optional[int] = None
    tomato_audience: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    where_to_watch: Optional[List[str]] = None
    languages: Optional[Union[str, List[str]]] = None
    countries: Optional[Union[str, List[str]]] = None
    collection: Optional[str] = None
    rt_score: Optional[int] = None
    last_tmdb_fetch_at: Optional[datetime] = None
    last_omdb_fetch_at: Optional[datetime] = None
    tmdb_etag: Optional[str] = None
    tmdb_payload_sha: Optional[str] = None
    omdb_payload_sha: Optional[str] = None
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
    keywords: List[str] = Field(default_factory=list)


class MovieLookupResponse(BaseModel):
    items: List[MovieLookupCandidate] = Field(default_factory=list)


class MovieSearchResponse(BaseModel):
    items: List[MovieRead]
    total: int
    page: int
    page_size: int
    facets: MovieFacets

    model_config = ConfigDict(from_attributes=True)


class MovieFlagCreate(BaseModel):
    reason: Optional[str] = None
    notes: Optional[str] = None


class MovieFlagRead(BaseModel):
    movie_id: int
    reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)
