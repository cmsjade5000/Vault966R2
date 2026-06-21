from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.movie_flag_create_reason import MovieFlagCreateReason
from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieFlagCreate")


@_attrs_define
class MovieFlagCreate:
    """
    Attributes:
        notes (None | str | Unset):
        reason (MovieFlagCreateReason | Unset):  Default: MovieFlagCreateReason.METADATA_CLEANUP.
    """

    notes: None | str | Unset = UNSET
    reason: MovieFlagCreateReason | Unset = MovieFlagCreateReason.METADATA_CLEANUP

    def to_dict(self) -> dict[str, Any]:
        notes: None | str | Unset
        if isinstance(self.notes, Unset):
            notes = UNSET
        else:
            notes = self.notes

        reason: str | Unset = UNSET
        if not isinstance(self.reason, Unset):
            reason = self.reason.value

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if notes is not UNSET:
            field_dict["notes"] = notes
        if reason is not UNSET:
            field_dict["reason"] = reason

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notes = _parse_notes(d.pop("notes", UNSET))

        _reason = d.pop("reason", UNSET)
        reason: MovieFlagCreateReason | Unset
        if isinstance(_reason, Unset):
            reason = UNSET
        else:
            reason = MovieFlagCreateReason(_reason)

        movie_flag_create = cls(
            notes=notes,
            reason=reason,
        )

        return movie_flag_create
