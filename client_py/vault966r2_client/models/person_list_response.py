from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.person_read import PersonRead


T = TypeVar("T", bound="PersonListResponse")


@_attrs_define
class PersonListResponse:
    """
    Attributes:
        items (list['PersonRead']):
        page (int):
        page_size (int):
        total (int):
    """

    items: list["PersonRead"]
    page: int
    page_size: int
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        page = self.page

        page_size = self.page_size

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.person_read import PersonRead

        d = dict(src_dict)
        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = PersonRead.from_dict(items_item_data)

            items.append(items_item)

        page = d.pop("page")

        page_size = d.pop("page_size")

        total = d.pop("total")

        person_list_response = cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
        )

        person_list_response.additional_properties = d
        return person_list_response

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
