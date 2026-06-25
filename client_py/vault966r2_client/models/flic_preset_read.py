from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.flic_filters import FlicFilters


T = TypeVar("T", bound="FlicPresetRead")


@_attrs_define
class FlicPresetRead:
    """
    Attributes:
        created_at (datetime.datetime):
        filters (FlicFilters):
        id (int):
        name (str):
    """

    created_at: datetime.datetime
    filters: FlicFilters
    id: int
    name: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        filters = self.filters.to_dict()

        id = self.id

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "filters": filters,
                "id": id,
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.flic_filters import FlicFilters

        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        filters = FlicFilters.from_dict(d.pop("filters"))

        id = d.pop("id")

        name = d.pop("name")

        flic_preset_read = cls(
            created_at=created_at,
            filters=filters,
            id=id,
            name=name,
        )

        flic_preset_read.additional_properties = d
        return flic_preset_read

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
