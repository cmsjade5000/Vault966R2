from __future__ import annotations

from typing import Optional, Union

from fastapi import HTTPException, status


def parse_optional_non_negative_int(
    value: Optional[Union[str, int]], field_name: str
) -> Optional[int]:
    """Convert query parameters to optional non-negative integers.

    FastAPI/Pydantic treats empty strings as invalid integers. The UI submits
    numeric filters as blank strings when users clear the fields, so we coerce
    those blanks to ``None`` while preserving validation for real numbers.
    """

    if value is None:
        return None

    if isinstance(value, int):
        candidate = value
    else:
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            candidate = int(stripped)
        except ValueError as exc:  # pragma: no cover - defensive branch
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=[
                    {
                        "type": "int_parsing",
                        "loc": ["query", field_name],
                        "msg": "Input should be a valid integer, unable to parse string as an integer",
                        "input": value,
                    }
                ],
            ) from exc

    if candidate < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "type": "greater_than_equal",
                    "loc": ["query", field_name],
                    "msg": "Input should be greater than or equal to 0",
                    "input": candidate,
                    "ctx": {"ge": 0},
                }
            ],
        )

    return candidate
