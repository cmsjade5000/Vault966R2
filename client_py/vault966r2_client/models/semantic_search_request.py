from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SemanticSearchRequest")


@_attrs_define
class SemanticSearchRequest:
    """
    Attributes:
        query (str):
        genres (list[str] | Unset):
        moods (list[str] | Unset):
        page (int | Unset):  Default: 1.
        page_size (int | Unset):  Default: 24.
        runtime_max (int | None | Unset):
        runtime_min (int | None | Unset):
        year_max (int | None | Unset):
        year_min (int | None | Unset):
    """

    query: str
    genres: list[str] | Unset = UNSET
    moods: list[str] | Unset = UNSET
    page: int | Unset = 1
    page_size: int | Unset = 24
    runtime_max: int | None | Unset = UNSET
    runtime_min: int | None | Unset = UNSET
    year_max: int | None | Unset = UNSET
    year_min: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        query = self.query

        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        moods: list[str] | Unset = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        page = self.page

        page_size = self.page_size

        runtime_max: int | None | Unset
        if isinstance(self.runtime_max, Unset):
            runtime_max = UNSET
        else:
            runtime_max = self.runtime_max

        runtime_min: int | None | Unset
        if isinstance(self.runtime_min, Unset):
            runtime_min = UNSET
        else:
            runtime_min = self.runtime_min

        year_max: int | None | Unset
        if isinstance(self.year_max, Unset):
            year_max = UNSET
        else:
            year_max = self.year_max

        year_min: int | None | Unset
        if isinstance(self.year_min, Unset):
            year_min = UNSET
        else:
            year_min = self.year_min

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "query": query,
            }
        )
        if genres is not UNSET:
            field_dict["genres"] = genres
        if moods is not UNSET:
            field_dict["moods"] = moods
        if page is not UNSET:
            field_dict["page"] = page
        if page_size is not UNSET:
            field_dict["page_size"] = page_size
        if runtime_max is not UNSET:
            field_dict["runtime_max"] = runtime_max
        if runtime_min is not UNSET:
            field_dict["runtime_min"] = runtime_min
        if year_max is not UNSET:
            field_dict["year_max"] = year_max
        if year_min is not UNSET:
            field_dict["year_min"] = year_min

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        query = d.pop("query")

        genres = cast(list[str], d.pop("genres", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

        page = d.pop("page", UNSET)

        page_size = d.pop("page_size", UNSET)

        def _parse_runtime_max(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime_max = _parse_runtime_max(d.pop("runtime_max", UNSET))

        def _parse_runtime_min(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime_min = _parse_runtime_min(d.pop("runtime_min", UNSET))

        def _parse_year_max(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year_max = _parse_year_max(d.pop("year_max", UNSET))

        def _parse_year_min(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year_min = _parse_year_min(d.pop("year_min", UNSET))

        semantic_search_request = cls(
            query=query,
            genres=genres,
            moods=moods,
            page=page,
            page_size=page_size,
            runtime_max=runtime_max,
            runtime_min=runtime_min,
            year_max=year_max,
            year_min=year_min,
        )

        semantic_search_request.additional_properties = d
        return semantic_search_request

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
