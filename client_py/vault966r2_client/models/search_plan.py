from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="SearchPlan")


@_attrs_define
class SearchPlan:
    """
    Attributes:
        genres (Union[Unset, list[str]]):
        moods (Union[Unset, list[str]]):
        order_by (Union[Unset, str]):  Default: 'title_asc'.
        q (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, int]):
        runtime_min (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        year_min (Union[None, Unset, int]):
    """

    genres: Union[Unset, list[str]] = UNSET
    moods: Union[Unset, list[str]] = UNSET
    order_by: Union[Unset, str] = "title_asc"
    q: Union[None, Unset, str] = UNSET
    runtime_max: Union[None, Unset, int] = UNSET
    runtime_min: Union[None, Unset, int] = UNSET
    year_max: Union[None, Unset, int] = UNSET
    year_min: Union[None, Unset, int] = UNSET

    def to_dict(self) -> dict[str, Any]:
        genres: Union[Unset, list[str]] = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        moods: Union[Unset, list[str]] = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        order_by = self.order_by

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

        runtime_min: Union[None, Unset, int]
        if isinstance(self.runtime_min, Unset):
            runtime_min = UNSET
        else:
            runtime_min = self.runtime_min

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

        field_dict.update({})
        if genres is not UNSET:
            field_dict["genres"] = genres
        if moods is not UNSET:
            field_dict["moods"] = moods
        if order_by is not UNSET:
            field_dict["order_by"] = order_by
        if q is not UNSET:
            field_dict["q"] = q
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
        genres = cast(list[str], d.pop("genres", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

        order_by = d.pop("order_by", UNSET)

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

        def _parse_runtime_min(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime_min = _parse_runtime_min(d.pop("runtime_min", UNSET))

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

        search_plan = cls(
            genres=genres,
            moods=moods,
            order_by=order_by,
            q=q,
            runtime_max=runtime_max,
            runtime_min=runtime_min,
            year_max=year_max,
            year_min=year_min,
        )

        return search_plan
