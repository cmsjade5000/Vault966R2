from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.flic_filters import FlicFilters


T = TypeVar("T", bound="FlicPresetCreate")


@_attrs_define
class FlicPresetCreate:
    """
    Attributes:
        filters (FlicFilters):
        name (str):
    """

    filters: FlicFilters
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        filters = self.filters.to_dict()

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "filters": filters,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.flic_filters import FlicFilters

        d = dict(src_dict)
        filters = FlicFilters.from_dict(d.pop("filters"))

        name = d.pop("name")

        flic_preset_create = cls(
            filters=filters,
            name=name,
        )

        flic_preset_create.additional_properties = d
        return flic_preset_create

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
