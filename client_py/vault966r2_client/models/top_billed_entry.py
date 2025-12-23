from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="TopBilledEntry")


@_attrs_define
class TopBilledEntry:
    """
    Attributes:
        name (str):
        character (Union[None, Unset, str]):
        imdb_id (Union[None, Unset, str]):
        person_id (Union[None, Unset, int]):
    """

    name: str
    character: Union[None, Unset, str] = UNSET
    imdb_id: Union[None, Unset, str] = UNSET
    person_id: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        character: Union[None, Unset, str]
        if isinstance(self.character, Unset):
            character = UNSET
        else:
            character = self.character

        imdb_id: Union[None, Unset, str]
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        person_id: Union[None, Unset, int]
        if isinstance(self.person_id, Unset):
            person_id = UNSET
        else:
            person_id = self.person_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if character is not UNSET:
            field_dict["character"] = character
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if person_id is not UNSET:
            field_dict["person_id"] = person_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        def _parse_character(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        character = _parse_character(d.pop("character", UNSET))

        def _parse_imdb_id(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        def _parse_person_id(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        person_id = _parse_person_id(d.pop("person_id", UNSET))

        top_billed_entry = cls(
            name=name,
            character=character,
            imdb_id=imdb_id,
            person_id=person_id,
        )

        top_billed_entry.additional_properties = d
        return top_billed_entry

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
