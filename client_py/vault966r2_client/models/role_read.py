from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role_type import RoleType
from ..types import UNSET, Unset

T = TypeVar("T", bound="RoleRead")


@_attrs_define
class RoleRead:
    """
    Attributes:
        id (int):
        movie_id (int):
        person_id (int):
        role_type (RoleType):
        billing_order (Union[None, Unset, int]):
        character_name (Union[None, Unset, str]):
    """

    id: int
    movie_id: int
    person_id: int
    role_type: RoleType
    billing_order: Union[None, Unset, int] = UNSET
    character_name: Union[None, Unset, str] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        movie_id = self.movie_id

        person_id = self.person_id

        role_type = self.role_type.value

        billing_order: Union[None, Unset, int]
        if isinstance(self.billing_order, Unset):
            billing_order = UNSET
        else:
            billing_order = self.billing_order

        character_name: Union[None, Unset, str]
        if isinstance(self.character_name, Unset):
            character_name = UNSET
        else:
            character_name = self.character_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "movie_id": movie_id,
                "person_id": person_id,
                "role_type": role_type,
            }
        )
        if billing_order is not UNSET:
            field_dict["billing_order"] = billing_order
        if character_name is not UNSET:
            field_dict["character_name"] = character_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        movie_id = d.pop("movie_id")

        person_id = d.pop("person_id")

        role_type = RoleType(d.pop("role_type"))

        def _parse_billing_order(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        billing_order = _parse_billing_order(d.pop("billing_order", UNSET))

        def _parse_character_name(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        character_name = _parse_character_name(d.pop("character_name", UNSET))

        role_read = cls(
            id=id,
            movie_id=movie_id,
            person_id=person_id,
            role_type=role_type,
            billing_order=billing_order,
            character_name=character_name,
        )

        role_read.additional_properties = d
        return role_read

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
