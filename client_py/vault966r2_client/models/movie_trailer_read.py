from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieTrailerRead")


@_attrs_define
class MovieTrailerRead:
    """
    Attributes:
        embed_url (str):
        key (str):
        site (str):
        url (str):
        name (None | str | Unset):
    """

    embed_url: str
    key: str
    site: str
    url: str
    name: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        embed_url = self.embed_url

        key = self.key

        site = self.site

        url = self.url

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "embed_url": embed_url,
                "key": key,
                "site": site,
                "url": url,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        embed_url = d.pop("embed_url")

        key = d.pop("key")

        site = d.pop("site")

        url = d.pop("url")

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        movie_trailer_read = cls(
            embed_url=embed_url,
            key=key,
            site=site,
            url=url,
            name=name,
        )

        movie_trailer_read.additional_properties = d
        return movie_trailer_read

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
