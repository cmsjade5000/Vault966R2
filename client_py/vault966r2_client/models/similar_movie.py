from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

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
        flic_score (Union[None, Unset, float]):
        poster_theme (Union[None, Unset, str]):
        poster_url (Union[None, Unset, str]):
        year (Union[None, Unset, int]):
    """

    id: int
    title: str
    flic_score: Union[None, Unset, float] = UNSET
    poster_theme: Union[None, Unset, str] = UNSET
    poster_url: Union[None, Unset, str] = UNSET
    year: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

        flic_score: Union[None, Unset, float]
        if isinstance(self.flic_score, Unset):
            flic_score = UNSET
        else:
            flic_score = self.flic_score

        poster_theme: Union[None, Unset, str]
        if isinstance(self.poster_theme, Unset):
            poster_theme = UNSET
        else:
            poster_theme = self.poster_theme

        poster_url: Union[None, Unset, str]
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        year: Union[None, Unset, int]
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
        if poster_theme is not UNSET:
            field_dict["poster_theme"] = poster_theme
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

        def _parse_flic_score(data: object) -> Union[None, Unset, float]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, float], data)

        flic_score = _parse_flic_score(d.pop("flic_score", UNSET))

        def _parse_poster_theme(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        poster_theme = _parse_poster_theme(d.pop("poster_theme", UNSET))

        def _parse_poster_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        similar_movie = cls(
            id=id,
            title=title,
            flic_score=flic_score,
            poster_theme=poster_theme,
            poster_url=poster_url,
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
