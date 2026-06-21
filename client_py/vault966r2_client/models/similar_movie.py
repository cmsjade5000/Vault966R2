from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SimilarMovie")


@_attrs_define
class SimilarMovie:
    """
    Attributes:
        id (int):
        title (str):
        flic_score (float | None | Unset):
        genres (list[str] | Unset):
        imdb_rating (float | None | Unset):
        poster_theme (None | str | Unset):
        poster_url (None | str | Unset):
        rt_score (int | None | Unset):
        year (int | None | Unset):
    """

    id: int
    title: str
    flic_score: float | None | Unset = UNSET
    genres: list[str] | Unset = UNSET
    imdb_rating: float | None | Unset = UNSET
    poster_theme: None | str | Unset = UNSET
    poster_url: None | str | Unset = UNSET
    rt_score: int | None | Unset = UNSET
    year: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        flic_score: float | None | Unset
        if isinstance(self.flic_score, Unset):
            flic_score = UNSET
        else:
            flic_score = self.flic_score

        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        imdb_rating: float | None | Unset
        if isinstance(self.imdb_rating, Unset):
            imdb_rating = UNSET
        else:
            imdb_rating = self.imdb_rating

        poster_theme: None | str | Unset
        if isinstance(self.poster_theme, Unset):
            poster_theme = UNSET
        else:
            poster_theme = self.poster_theme

        poster_url: None | str | Unset
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        rt_score: int | None | Unset
        if isinstance(self.rt_score, Unset):
            rt_score = UNSET
        else:
            rt_score = self.rt_score

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
        if flic_score is not UNSET:
            field_dict["flic_score"] = flic_score
        if genres is not UNSET:
            field_dict["genres"] = genres
        if imdb_rating is not UNSET:
            field_dict["imdb_rating"] = imdb_rating
        if poster_theme is not UNSET:
            field_dict["poster_theme"] = poster_theme
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if rt_score is not UNSET:
            field_dict["rt_score"] = rt_score
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        def _parse_flic_score(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        flic_score = _parse_flic_score(d.pop("flic_score", UNSET))

        genres = cast(list[str], d.pop("genres", UNSET))

        def _parse_imdb_rating(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        imdb_rating = _parse_imdb_rating(d.pop("imdb_rating", UNSET))

        def _parse_poster_theme(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        poster_theme = _parse_poster_theme(d.pop("poster_theme", UNSET))

        def _parse_poster_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        def _parse_rt_score(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        rt_score = _parse_rt_score(d.pop("rt_score", UNSET))

        def _parse_year(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year = _parse_year(d.pop("year", UNSET))

        similar_movie = cls(
            id=id,
            title=title,
            flic_score=flic_score,
            genres=genres,
            imdb_rating=imdb_rating,
            poster_theme=poster_theme,
            poster_url=poster_url,
            rt_score=rt_score,
            year=year,
        )

        similar_movie.additional_properties = d
        return similar_movie

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
