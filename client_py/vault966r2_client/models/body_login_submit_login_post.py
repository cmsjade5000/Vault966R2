from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="BodyLoginSubmitLoginPost")


@_attrs_define
class BodyLoginSubmitLoginPost:
    """
    Attributes:
        access_key (None | str | Unset):
        passcode (None | str | Unset):
        profile_id (int | None | Unset):
    """

    access_key: None | str | Unset = UNSET
    passcode: None | str | Unset = UNSET
    profile_id: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        access_key: None | str | Unset
        if isinstance(self.access_key, Unset):
            access_key = UNSET
        else:
            access_key = self.access_key

        passcode: None | str | Unset
        if isinstance(self.passcode, Unset):
            passcode = UNSET
        else:
            passcode = self.passcode

        profile_id: int | None | Unset
        if isinstance(self.profile_id, Unset):
            profile_id = UNSET
        else:
            profile_id = self.profile_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if access_key is not UNSET:
            field_dict["access_key"] = access_key
        if passcode is not UNSET:
            field_dict["passcode"] = passcode
        if profile_id is not UNSET:
            field_dict["profile_id"] = profile_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_access_key(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        access_key = _parse_access_key(d.pop("access_key", UNSET))

        def _parse_passcode(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        passcode = _parse_passcode(d.pop("passcode", UNSET))

        def _parse_profile_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        profile_id = _parse_profile_id(d.pop("profile_id", UNSET))

        body_login_submit_login_post = cls(
            access_key=access_key,
            passcode=passcode,
            profile_id=profile_id,
        )

        body_login_submit_login_post.additional_properties = d
        return body_login_submit_login_post

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
