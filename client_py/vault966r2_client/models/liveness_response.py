from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="LivenessResponse")


@_attrs_define
class LivenessResponse:
    """
    Attributes:
        status (Literal['alive']):
    """

    status: Literal["alive"]

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
        status = cast(Literal["alive"], d.pop("status"))
        if status != "alive":
            raise ValueError(f"status must match const 'alive', got '{status}'")

        liveness_response = cls(
            status=status,
        )

        return liveness_response
