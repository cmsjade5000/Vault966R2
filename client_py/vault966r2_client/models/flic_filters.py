from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="FlicFilters")


@_attrs_define
class FlicFilters:
    """
    Attributes:
        genres (list[str] | Unset):
        moods (list[str] | Unset):
        q (None | str | Unset):
        runtime_max (int | None | Unset):
        year_max (int | None | Unset):
        year_min (int | None | Unset):
    """

    genres: list[str] | Unset = UNSET
    moods: list[str] | Unset = UNSET
    q: None | str | Unset = UNSET
    runtime_max: int | None | Unset = UNSET
    year_max: int | None | Unset = UNSET
    year_min: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        moods: list[str] | Unset = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        q: None | str | Unset
        if isinstance(self.q, Unset):
            q = UNSET
        else:
            q = self.q

        runtime_max: int | None | Unset
        if isinstance(self.runtime_max, Unset):
            runtime_max = UNSET
        else:
            runtime_max = self.runtime_max

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
        field_dict.update({})
        if genres is not UNSET:
            field_dict["genres"] = genres
        if moods is not UNSET:
            field_dict["moods"] = moods
        if q is not UNSET:
            field_dict["q"] = q
        if runtime_max is not UNSET:
            field_dict["runtime_max"] = runtime_max
        if year_max is not UNSET:
            field_dict["year_max"] = year_max
        if year_min is not UNSET:
            field_dict["year_min"] = year_min

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        genres = cast(list[str], d.pop("genres", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

        def _parse_q(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        q = _parse_q(d.pop("q", UNSET))

        def _parse_runtime_max(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime_max = _parse_runtime_max(d.pop("runtime_max", UNSET))

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

        flic_filters = cls(
            genres=genres,
            moods=moods,
            q=q,
            runtime_max=runtime_max,
            year_max=year_max,
            year_min=year_min,
        )

        flic_filters.additional_properties = d
        return flic_filters

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
