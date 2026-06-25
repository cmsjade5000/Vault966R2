from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AssistantMovie")


@_attrs_define
class AssistantMovie:
    """
    Attributes:
        id (int):
        title (str):
        genres (list[str] | Unset):
        imdb_rating (float | None | Unset):
        moods (list[str] | Unset):
        rt_score (int | None | Unset):
        runtime (int | None | Unset):
        year (int | None | Unset):
    """

    id: int
    title: str
    genres: list[str] | Unset = UNSET
    imdb_rating: float | None | Unset = UNSET
    moods: list[str] | Unset = UNSET
    rt_score: int | None | Unset = UNSET
    runtime: int | None | Unset = UNSET
    year: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        imdb_rating: float | None | Unset
        if isinstance(self.imdb_rating, Unset):
            imdb_rating = UNSET
        else:
            imdb_rating = self.imdb_rating

        moods: list[str] | Unset = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        rt_score: int | None | Unset
        if isinstance(self.rt_score, Unset):
            rt_score = UNSET
        else:
            rt_score = self.rt_score

        runtime: int | None | Unset
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        year: int | None | Unset
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "title": title,
            }
        )
        if genres is not UNSET:
            field_dict["genres"] = genres
        if imdb_rating is not UNSET:
            field_dict["imdb_rating"] = imdb_rating
        if moods is not UNSET:
            field_dict["moods"] = moods
        if rt_score is not UNSET:
            field_dict["rt_score"] = rt_score
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        genres = cast(list[str], d.pop("genres", UNSET))

        def _parse_imdb_rating(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        imdb_rating = _parse_imdb_rating(d.pop("imdb_rating", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

        def _parse_rt_score(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        rt_score = _parse_rt_score(d.pop("rt_score", UNSET))

        def _parse_runtime(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_year(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year = _parse_year(d.pop("year", UNSET))

        assistant_movie = cls(
            id=id,
            title=title,
            genres=genres,
            imdb_rating=imdb_rating,
            moods=moods,
            rt_score=rt_score,
            runtime=runtime,
            year=year,
        )

        assistant_movie.additional_properties = d
        return assistant_movie

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
