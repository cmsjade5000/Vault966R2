from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ErrorResponse")


@_attrs_define
class ErrorResponse:
    """
    Attributes:
        error_code (str):
        message (str):
        request_id (str):
    """

    error_code: str
    message: str
    request_id: str

    def to_dict(self) -> dict[str, Any]:
        error_code = self.error_code

        message = self.message

        request_id = self.request_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "error_code": error_code,
                "message": message,
                "request_id": request_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        error_code = d.pop("error_code")

        message = d.pop("message")

        request_id = d.pop("request_id")

        error_response = cls(
            error_code=error_code,
            message=message,
            request_id=request_id,
        )

        return error_response
