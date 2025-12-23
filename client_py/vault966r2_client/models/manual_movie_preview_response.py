from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ManualMoviePreviewResponse")


@_attrs_define
class ManualMoviePreviewResponse:
    """
    Attributes:
        title (str):
        backdrop_url (Union[None, Unset, str]):
        genres (Union[Unset, list[str]]):
        imdb_id (Union[None, Unset, str]):
        keywords (Union[Unset, list[str]]):
        overview (Union[None, Unset, str]):
        poster_url (Union[None, Unset, str]):
        release_date (Union[None, Unset, str]):
        runtime (Union[None, Unset, int]):
        source (Union[None, Unset, str]):
        tmdb_id (Union[None, Unset, int]):
        where_to_watch (Union[Unset, list[str]]):
        year (Union[None, Unset, int]):
    """

    title: str
    backdrop_url: Union[None, Unset, str] = UNSET
    genres: Union[Unset, list[str]] = UNSET
    imdb_id: Union[None, Unset, str] = UNSET
    keywords: Union[Unset, list[str]] = UNSET
    overview: Union[None, Unset, str] = UNSET
    poster_url: Union[None, Unset, str] = UNSET
    release_date: Union[None, Unset, str] = UNSET
    runtime: Union[None, Unset, int] = UNSET
    source: Union[None, Unset, str] = UNSET
    tmdb_id: Union[None, Unset, int] = UNSET
    where_to_watch: Union[Unset, list[str]] = UNSET
    year: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        title = self.title

        backdrop_url: Union[None, Unset, str]
        if isinstance(self.backdrop_url, Unset):
            backdrop_url = UNSET
        else:
            backdrop_url = self.backdrop_url

        genres: Union[Unset, list[str]] = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        imdb_id: Union[None, Unset, str]
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        keywords: Union[Unset, list[str]] = UNSET
        if not isinstance(self.keywords, Unset):
            keywords = self.keywords

        overview: Union[None, Unset, str]
        if isinstance(self.overview, Unset):
            overview = UNSET
        else:
            overview = self.overview

        poster_url: Union[None, Unset, str]
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        release_date: Union[None, Unset, str]
        if isinstance(self.release_date, Unset):
            release_date = UNSET
        else:
            release_date = self.release_date

        runtime: Union[None, Unset, int]
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        source: Union[None, Unset, str]
        if isinstance(self.source, Unset):
            source = UNSET
        else:
            source = self.source

        tmdb_id: Union[None, Unset, int]
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        where_to_watch: Union[Unset, list[str]] = UNSET
        if not isinstance(self.where_to_watch, Unset):
            where_to_watch = self.where_to_watch

        year: Union[None, Unset, int]
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "title": title,
            }
        )
        if backdrop_url is not UNSET:
            field_dict["backdrop_url"] = backdrop_url
        if genres is not UNSET:
            field_dict["genres"] = genres
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if keywords is not UNSET:
            field_dict["keywords"] = keywords
        if overview is not UNSET:
            field_dict["overview"] = overview
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if release_date is not UNSET:
            field_dict["release_date"] = release_date
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if source is not UNSET:
            field_dict["source"] = source
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
        if where_to_watch is not UNSET:
            field_dict["where_to_watch"] = where_to_watch
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        title = d.pop("title")

        def _parse_backdrop_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        backdrop_url = _parse_backdrop_url(d.pop("backdrop_url", UNSET))

        genres = cast(list[str], d.pop("genres", UNSET))

        def _parse_imdb_id(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        keywords = cast(list[str], d.pop("keywords", UNSET))

        def _parse_overview(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        overview = _parse_overview(d.pop("overview", UNSET))

        def _parse_poster_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        def _parse_release_date(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        release_date = _parse_release_date(d.pop("release_date", UNSET))

        def _parse_runtime(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_source(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        source = _parse_source(d.pop("source", UNSET))

        def _parse_tmdb_id(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        where_to_watch = cast(list[str], d.pop("where_to_watch", UNSET))

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        manual_movie_preview_response = cls(
            title=title,
            backdrop_url=backdrop_url,
            genres=genres,
            imdb_id=imdb_id,
            keywords=keywords,
            overview=overview,
            poster_url=poster_url,
            release_date=release_date,
            runtime=runtime,
            source=source,
            tmdb_id=tmdb_id,
            where_to_watch=where_to_watch,
            year=year,
        )

        manual_movie_preview_response.additional_properties = d
        return manual_movie_preview_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
