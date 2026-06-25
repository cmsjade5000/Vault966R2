from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class LenientJSONText(TypeDecorator):
    """
    SQLite compatibility type for columns that are JSONB in Postgres but were historically
    stored as raw TEXT in the repo-provided SQLite dumps.

    - Accepts Python lists/dicts (stores JSON string)
    - Accepts raw strings (stores as-is)
    - On read, attempts JSON decoding; if it fails, returns the raw string.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value)
        except TypeError:
            return json.dumps(str(value))

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value


__all__ = ["LenientJSONText"]
