from __future__ import annotations

from collections.abc import Mapping, Sequence as SequenceABC
from typing import Any, Iterable, List, Sequence


def normalize_provider(label: str | None) -> str:
    if not label:
        return ""
    cleaned = label.strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in {"vudu", "in vudu"}:
        return "Vudu"
    return cleaned


def merge_providers(*lists: Iterable[str | None]) -> List[str]:
    seen: list[str] = []
    for provider_list in lists:
        if not provider_list:
            continue
        for item in provider_list:
            normalized = normalize_provider(item)
            if normalized and normalized not in seen:
                seen.append(normalized)
    return seen


def _iter_provider_candidates(value: Any) -> Iterable[Any]:
    if value is None:
        return
    if isinstance(value, str):
        for part in value.replace(";", ",").split(","):
            yield part
        return
    if isinstance(value, Mapping):
        # Common TMDb payload shape: {"flatrate": [...], "rent": [...]}
        provider_name = value.get("provider_name") or value.get("name")
        if provider_name:
            yield provider_name
        for sub_value in value.values():
            if sub_value is value:
                continue
            yield from _iter_provider_candidates(sub_value)
        return
    if isinstance(value, SequenceABC) and not isinstance(value, (bytes, bytearray)):
        for item in value:
            yield from _iter_provider_candidates(item)
        return
    yield value


def split_providers(value: Sequence[str] | str | None) -> List[str]:
    normalized: list[str] = []
    for candidate in _iter_provider_candidates(value):
        normalized_item = normalize_provider(str(candidate) if candidate is not None else None)
        if normalized_item and normalized_item not in normalized:
            normalized.append(normalized_item)
    return normalized


def serialize_providers(values: Iterable[str] | None) -> str | None:
    merged = merge_providers(values)
    return "; ".join(merged) if merged else None


__all__ = ["normalize_provider", "merge_providers", "split_providers", "serialize_providers"]
