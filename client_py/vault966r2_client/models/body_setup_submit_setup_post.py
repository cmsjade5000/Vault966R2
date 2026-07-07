from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="BodySetupSubmitSetupPost")


@_attrs_define
class BodySetupSubmitSetupPost:
    """
    Attributes:
        access_key (str | Unset):  Default: ''.
        passcode (str | Unset):  Default: ''.
        passcode_confirm (str | Unset):  Default: ''.
        profile_name (str | Unset):  Default: ''.
    """

    access_key: str | Unset = ""
    passcode: str | Unset = ""
    passcode_confirm: str | Unset = ""
    profile_name: str | Unset = ""
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access_key = self.access_key

        passcode = self.passcode

        passcode_confirm = self.passcode_confirm

        profile_name = self.profile_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if access_key is not UNSET:
            field_dict["access_key"] = access_key
        if passcode is not UNSET:
            field_dict["passcode"] = passcode
        if passcode_confirm is not UNSET:
            field_dict["passcode_confirm"] = passcode_confirm
        if profile_name is not UNSET:
            field_dict["profile_name"] = profile_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        access_key = d.pop("access_key", UNSET)

        passcode = d.pop("passcode", UNSET)

        passcode_confirm = d.pop("passcode_confirm", UNSET)

        profile_name = d.pop("profile_name", UNSET)

        body_setup_submit_setup_post = cls(
            access_key=access_key,
            passcode=passcode,
            passcode_confirm=passcode_confirm,
            profile_name=profile_name,
        )

        body_setup_submit_setup_post.additional_properties = d
        return body_setup_submit_setup_post

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
