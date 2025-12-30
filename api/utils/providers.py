from __future__ import annotations

import re
from collections.abc import Iterable as IterableCollection, Mapping
from typing import Any, Iterable, List


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


def _tokenize_provider_text(value: str) -> List[str]:
    parts = re.split(r"[;,]", value)
    tokens: List[str] = []
    for part in parts:
        candidate = part.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in {
            "n/a",
            "na",
            "none",
            "null",
            "unknown",
            "true",
            "false",
            "link",
            "links",
            "logo_path",
            "provider_id",
            "providerid",
            "metadata",
            "results",
            "last_updated",
        }:
            continue
        if candidate.startswith("/"):
            continue
        if "://" in candidate or lowered.startswith("www."):
            continue
        if all(ch.isdigit() for ch in candidate):
            continue
        if not any(ch.isalpha() for ch in candidate):
            continue
        tokens.append(candidate)
    return tokens


def collect_provider_tokens(value: Any) -> List[str]:
    """Return a flattened list of provider-like strings from arbitrary input."""

    def _collect(current: Any, visited: set[int]) -> List[str]:
        if current is None:
            return []

        if isinstance(current, str):
            return _tokenize_provider_text(current)

        if isinstance(current, (bytes, bytearray)):
            try:
                decoded = current.decode("utf-8")  # type: ignore[union-attr]
            except UnicodeDecodeError:
                decoded = current.decode("latin-1", errors="ignore")  # type: ignore[union-attr]
            return _tokenize_provider_text(decoded)

        if isinstance(current, (int, float, bool)):
            return []

        if isinstance(current, Mapping):
            obj_id = id(current)
            if obj_id in visited:
                return []
            visited.add(obj_id)

            tokens: List[str] = []
            for key in ("provider_name", "name", "display_name", "label"):
                if key in current:
                    tokens.extend(_collect(current[key], visited))
            if tokens:
                return tokens

            for item in current.values():
                tokens.extend(_collect(item, visited))
            if tokens:
                return tokens

            for key in current.keys():
                tokens.extend(_collect(key, visited))
            return tokens

        if isinstance(current, IterableCollection):
            obj_id = id(current)
            if obj_id in visited:
                return []
            visited.add(obj_id)

            tokens: List[str] = []
            for item in current:
                tokens.extend(_collect(item, visited))
            return tokens

        text = str(current).strip()
        if not text:
            return []
        return _tokenize_provider_text(text)

    return _collect(value, set())


def split_providers(value: Any) -> List[str]:
    tokens = collect_provider_tokens(value)
    normalized: list[str] = []
    for item in tokens:
        normalized_item = normalize_provider(item)
        if normalized_item and normalized_item not in normalized:
            normalized.append(normalized_item)
    return normalized


def serialize_providers(values: Iterable[str] | None) -> str | None:
    merged = merge_providers(values)
    return "; ".join(merged) if merged else None


__all__ = [
    "normalize_provider",
    "merge_providers",
    "collect_provider_tokens",
    "split_providers",
    "serialize_providers",
]
