from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Iterator, List


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


def _iter_provider_candidates(value: Any) -> Iterator[str]:
    if value is None:
        return
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_provider_candidates(item)
        return
    if isinstance(value, str):
        for token in value.replace(";", ",").split(","):
            stripped = token.strip()
            if stripped:
                yield stripped
        return
    if isinstance(value, Iterable):
        for item in value:
            yield from _iter_provider_candidates(item)
        return
    text = str(value).strip()
    if text:
        yield text


def merge_providers(*lists: Any) -> List[str]:
    seen: list[str] = []
    for provider_list in lists:
        for item in _iter_provider_candidates(provider_list):
            normalized = normalize_provider(item)
            if normalized and normalized not in seen:
                seen.append(normalized)
    return seen


def split_providers(value: Any) -> List[str]:
    return merge_providers(value)


def serialize_providers(values: Iterable[str] | None) -> str | None:
    merged = merge_providers(values)
    return "; ".join(merged) if merged else None


__all__ = ["normalize_provider", "merge_providers", "split_providers", "serialize_providers"]
