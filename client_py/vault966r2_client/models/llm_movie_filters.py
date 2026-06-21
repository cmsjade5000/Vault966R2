from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="LlmMovieFilters")


@_attrs_define
class LlmMovieFilters:
    """
    Attributes:
        genres (list[str] | Unset):
        moods (list[str] | Unset):
        order_by (str | Unset):  Default: 'title_asc'.
        q (None | str | Unset):
        runtime_max (int | None | Unset):
        runtime_min (int | None | Unset):
        year_max (int | None | Unset):
        year_min (int | None | Unset):
    """

    genres: list[str] | Unset = UNSET
    moods: list[str] | Unset = UNSET
    order_by: str | Unset = "title_asc"
    q: None | str | Unset = UNSET
    runtime_max: int | None | Unset = UNSET
    runtime_min: int | None | Unset = UNSET
    year_max: int | None | Unset = UNSET
    year_min: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        moods: list[str] | Unset = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        order_by = self.order_by

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

        llm_movie_filters = cls(
            genres=genres,
            moods=moods,
            order_by=order_by,
            q=q,
            runtime_max=runtime_max,
            runtime_min=runtime_min,
            year_max=year_max,
            year_min=year_min,
        )

        return llm_movie_filters
