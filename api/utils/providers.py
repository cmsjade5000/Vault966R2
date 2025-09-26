from __future__ import annotations

from typing import Iterable, List, Sequence


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


def split_providers(value: Sequence[str] | str | None) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = value.replace(";", ",").split(",")
    else:
        candidates = value
    normalized: list[str] = []
    for item in candidates:
        normalized_item = normalize_provider(item)
        if normalized_item and normalized_item not in normalized:
            normalized.append(normalized_item)
    return normalized


def serialize_providers(values: Iterable[str] | None) -> str | None:
    merged = merge_providers(values)
    return "; ".join(merged) if merged else None


__all__ = ["normalize_provider", "merge_providers", "split_providers", "serialize_providers"]
