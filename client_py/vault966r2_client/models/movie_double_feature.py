from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.movie_read import MovieRead


T = TypeVar("T", bound="MovieDoubleFeature")


@_attrs_define
class MovieDoubleFeature:
    """
    Attributes:
        primary (MovieRead):
        runtime_cap (int):
        secondary (MovieRead):
        total_runtime (str):
    """

    primary: MovieRead
    runtime_cap: int
    secondary: MovieRead
    total_runtime: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        primary = self.primary.to_dict()

        runtime_cap = self.runtime_cap

        secondary = self.secondary.to_dict()

        total_runtime = self.total_runtime

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "primary": primary,
                "runtime_cap": runtime_cap,
                "secondary": secondary,
                "total_runtime": total_runtime,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.movie_read import MovieRead

        d = dict(src_dict)
        primary = MovieRead.from_dict(d.pop("primary"))

        runtime_cap = d.pop("runtime_cap")

        secondary = MovieRead.from_dict(d.pop("secondary"))

        total_runtime = d.pop("total_runtime")

        movie_double_feature = cls(
            primary=primary,
            runtime_cap=runtime_cap,
            secondary=secondary,
            total_runtime=total_runtime,
        )

        movie_double_feature.additional_properties = d
        return movie_double_feature

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
