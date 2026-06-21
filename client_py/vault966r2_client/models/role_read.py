from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role_type import RoleType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.person_read import PersonRead


T = TypeVar("T", bound="RoleRead")


@_attrs_define
class RoleRead:
    """
    Attributes:
        id (int):
        movie_id (int):
        person (PersonRead):
        person_id (int):
        role_type (RoleType):
        billing_order (int | None | Unset):
        character_name (None | str | Unset):
    """

    id: int
    movie_id: int
    person: PersonRead
    person_id: int
    role_type: RoleType
    billing_order: int | None | Unset = UNSET
    character_name: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        movie_id = self.movie_id

        person = self.person.to_dict()

        person_id = self.person_id

        role_type = self.role_type.value

        billing_order: int | None | Unset
        if isinstance(self.billing_order, Unset):
            billing_order = UNSET
        else:
            billing_order = self.billing_order

        character_name: None | str | Unset
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
                "person": person,
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
        from ..models.person_read import PersonRead

        d = dict(src_dict)
        id = d.pop("id")

        movie_id = d.pop("movie_id")

        person = PersonRead.from_dict(d.pop("person"))

        person_id = d.pop("person_id")

        role_type = RoleType(d.pop("role_type"))

        def _parse_billing_order(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        billing_order = _parse_billing_order(d.pop("billing_order", UNSET))

        def _parse_character_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        character_name = _parse_character_name(d.pop("character_name", UNSET))

        role_read = cls(
            id=id,
            movie_id=movie_id,
            person=person,
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
