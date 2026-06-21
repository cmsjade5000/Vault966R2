from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieFlagRead")


@_attrs_define
class MovieFlagRead:
    """
    Attributes:
        created_at (datetime.datetime):
        movie_id (int):
        updated_at (datetime.datetime):
        notes (None | str | Unset):
        reason (None | str | Unset):
        reported_by_profile_id (int | None | Unset):
    """

    created_at: datetime.datetime
    movie_id: int
    updated_at: datetime.datetime
    notes: None | str | Unset = UNSET
    reason: None | str | Unset = UNSET
    reported_by_profile_id: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at = self.created_at.isoformat()

        movie_id = self.movie_id

        updated_at = self.updated_at.isoformat()

        notes: None | str | Unset
        if isinstance(self.notes, Unset):
            notes = UNSET
        else:
            notes = self.notes

        reason: None | str | Unset
        if isinstance(self.reason, Unset):
            reason = UNSET
        else:
            reason = self.reason

        reported_by_profile_id: int | None | Unset
        if isinstance(self.reported_by_profile_id, Unset):
            reported_by_profile_id = UNSET
        else:
            reported_by_profile_id = self.reported_by_profile_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "created_at": created_at,
                "movie_id": movie_id,
                "updated_at": updated_at,
            }
        )
        if notes is not UNSET:
            field_dict["notes"] = notes
        if reason is not UNSET:
            field_dict["reason"] = reason
        if reported_by_profile_id is not UNSET:
            field_dict["reported_by_profile_id"] = reported_by_profile_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        movie_id = d.pop("movie_id")

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        def _parse_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notes = _parse_notes(d.pop("notes", UNSET))

        def _parse_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reason = _parse_reason(d.pop("reason", UNSET))

        def _parse_reported_by_profile_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        reported_by_profile_id = _parse_reported_by_profile_id(d.pop("reported_by_profile_id", UNSET))

        movie_flag_read = cls(
            created_at=created_at,
            movie_id=movie_id,
            updated_at=updated_at,
            notes=notes,
            reason=reason,
            reported_by_profile_id=reported_by_profile_id,
        )

        movie_flag_read.additional_properties = d
        return movie_flag_read

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
