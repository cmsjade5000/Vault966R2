from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieCreate")


@_attrs_define
class MovieCreate:
    """
    Attributes:
        title (str):
        backdrop_url (Union[None, Unset, str]):
        genres (Union[Unset, list[str]]):
        imdb_id (Union[None, Unset, str]):
        moods (Union[Unset, list[str]]):
        plot (Union[None, Unset, str]):
        poster_url (Union[None, Unset, str]):
        runtime (Union[None, Unset, int]):
        tmdb_id (Union[None, Unset, int]):
        year (Union[None, Unset, int]):
    """

    title: str
    backdrop_url: Union[None, Unset, str] = UNSET
    genres: Union[Unset, list[str]] = UNSET
    imdb_id: Union[None, Unset, str] = UNSET
    moods: Union[Unset, list[str]] = UNSET
    plot: Union[None, Unset, str] = UNSET
    poster_url: Union[None, Unset, str] = UNSET
    runtime: Union[None, Unset, int] = UNSET
    tmdb_id: Union[None, Unset, int] = UNSET
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

        moods: Union[Unset, list[str]] = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        plot: Union[None, Unset, str]
        if isinstance(self.plot, Unset):
            plot = UNSET
        else:
            plot = self.plot

        poster_url: Union[None, Unset, str]
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        runtime: Union[None, Unset, int]
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        tmdb_id: Union[None, Unset, int]
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

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
        if moods is not UNSET:
            field_dict["moods"] = moods
        if plot is not UNSET:
            field_dict["plot"] = plot
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
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

        moods = cast(list[str], d.pop("moods", UNSET))

        def _parse_plot(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        plot = _parse_plot(d.pop("plot", UNSET))

        def _parse_poster_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        def _parse_runtime(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_tmdb_id(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        movie_create = cls(
            title=title,
            backdrop_url=backdrop_url,
            genres=genres,
            imdb_id=imdb_id,
            moods=moods,
            plot=plot,
            poster_url=poster_url,
            runtime=runtime,
            tmdb_id=tmdb_id,
            year=year,
        )

        movie_create.additional_properties = d
        return movie_create

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
