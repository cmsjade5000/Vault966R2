from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="ReadinessResponse")


@_attrs_define
class ReadinessResponse:
    """
    Attributes:
        status (Literal['ready']):
    """

    status: Literal["ready"]

    def to_dict(self) -> dict[str, Any]:
        status = self.status

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        status = cast(Literal["ready"], d.pop("status"))
        if status != "ready":
            raise ValueError(f"status must match const 'ready', got '{status}'")

        readiness_response = cls(
            status=status,
        )

        return readiness_response
