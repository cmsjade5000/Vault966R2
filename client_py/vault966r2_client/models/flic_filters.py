from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="FlicFilters")


@_attrs_define
class FlicFilters:
    """
    Attributes:
        genres (Union[Unset, list[str]]):
        moods (Union[Unset, list[str]]):
        q (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        year_min (Union[None, Unset, int]):
    """

    genres: Union[Unset, list[str]] = UNSET
    moods: Union[Unset, list[str]] = UNSET
    q: Union[None, Unset, str] = UNSET
    runtime_max: Union[None, Unset, int] = UNSET
    year_max: Union[None, Unset, int] = UNSET
    year_min: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        genres: Union[Unset, list[str]] = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        moods: Union[Unset, list[str]] = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        q: Union[None, Unset, str]
        if isinstance(self.q, Unset):
            q = UNSET
        else:
            q = self.q

        runtime_max: Union[None, Unset, int]
        if isinstance(self.runtime_max, Unset):
            runtime_max = UNSET
        else:
            runtime_max = self.runtime_max

        year_max: Union[None, Unset, int]
        if isinstance(self.year_max, Unset):
            year_max = UNSET
        else:
            year_max = self.year_max

        year_min: Union[None, Unset, int]
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

        def _parse_q(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        q = _parse_q(d.pop("q", UNSET))

        def _parse_runtime_max(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime_max = _parse_runtime_max(d.pop("runtime_max", UNSET))

        def _parse_year_max(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year_max = _parse_year_max(d.pop("year_max", UNSET))

        def _parse_year_min(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

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
