from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieMatchApplyResponse")


@_attrs_define
class MovieMatchApplyResponse:
    """
    Attributes:
        flag_resolved (bool):
        message (str):
        movie_id (int):
        title (str):
        imdb_id (None | str | Unset):
        tmdb_id (int | None | Unset):
        vault_id (None | str | Unset):
    """

    flag_resolved: bool
    message: str
    movie_id: int
    title: str
    imdb_id: None | str | Unset = UNSET
    tmdb_id: int | None | Unset = UNSET
    vault_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        flag_resolved = self.flag_resolved

        message = self.message

        movie_id = self.movie_id

        title = self.title

        imdb_id: None | str | Unset
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        tmdb_id: int | None | Unset
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        vault_id: None | str | Unset
        if isinstance(self.vault_id, Unset):
            vault_id = UNSET
        else:
            vault_id = self.vault_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "flag_resolved": flag_resolved,
                "message": message,
                "movie_id": movie_id,
                "title": title,
            }
        )
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
        if vault_id is not UNSET:
            field_dict["vault_id"] = vault_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        flag_resolved = d.pop("flag_resolved")

        message = d.pop("message")

        movie_id = d.pop("movie_id")

        title = d.pop("title")

        def _parse_imdb_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        def _parse_tmdb_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_vault_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        vault_id = _parse_vault_id(d.pop("vault_id", UNSET))

        movie_match_apply_response = cls(
            flag_resolved=flag_resolved,
            message=message,
            movie_id=movie_id,
            title=title,
            imdb_id=imdb_id,
            tmdb_id=tmdb_id,
            vault_id=vault_id,
        )

        movie_match_apply_response.additional_properties = d
        return movie_match_apply_response

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
