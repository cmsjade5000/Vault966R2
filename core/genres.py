from __future__ import annotations

"""Helpers for keeping genre normalization consistent across services and templates."""

from typing import Iterable, List
import re

# Allow splitting composite labels like "War; Drama" or "Sci-Fi / Fantasy".
_SPLIT_PATTERN = re.compile(r"[\\/|;&]")
_WORD_TOKEN_PATTERN = re.compile(r"[^a-z0-9+]+")

# Map lowercase tokens to their canonical display labels.
_SYNONYM_MAP: dict[str, str] = {
    "sci fi": "Science Fiction",
    "sci-fi": "Science Fiction",
    "science fiction": "Science Fiction",
    "science-fiction": "Science Fiction",
    "scifi": "Science Fiction",
    "kids": "Family",
    "children": "Family",
    "kids & family": "Family",
    "kid friendly": "Family",
    "bio": "Biography",
    "biopic": "Biography",
    "history": "History",
    "historical": "History",
    "doc": "Documentary",
    "docu": "Documentary",
    "tv movie": "TV Movie",
    "thrillers": "Thriller",
    "rom-com": "Romance",
    "romcom": "Romance",
}


def _canonical_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered in _SYNONYM_MAP:
        return _SYNONYM_MAP[lowered]
    # Preserve acronyms like "R&B" and already-title-cased names.
    if cleaned.isupper() and len(cleaned) <= 5:
        return cleaned
    # Title-case short words but leave existing capitalization for others.
    if cleaned == cleaned.lower():
        return cleaned.title()
    return cleaned


def split_and_normalize(raw: Iterable[str]) -> List[str]:
    """Split composite genre strings and return canonical, de-duplicated labels."""
    seen: list[str] = []
    for item in raw:
        if not item:
            continue
        parts = _SPLIT_PATTERN.split(item)
        if len(parts) == 1:
            parts = [item]
        for part in parts:
            label = _canonical_label(part)
            if label and label.lower() != "nan" and label not in seen:
                seen.append(label)
    return seen


def tokens_for_theme(raw: Iterable[str]) -> List[str]:
    """Return normalized lowercase tokens for poster theme selection."""
    tokens_list: list[str] = []
    for label in split_and_normalize(raw):
        lowered = label.lower()
        if lowered:
            if lowered not in tokens_list:
                tokens_list.append(lowered)
        for chunk in _WORD_TOKEN_PATTERN.split(lowered):
            if chunk:
                if chunk not in tokens_list:
                    tokens_list.append(chunk)
    return tokens_list


def search_terms_for_label(label: str) -> List[str]:
    canonical = _canonical_label(label)
    if not canonical:
        return []
    lowered = canonical.lower()
    terms: set[str] = {lowered}
    for raw, target in _SYNONYM_MAP.items():
        if target == canonical:
            terms.add(raw.lower())
    return sorted(terms)


__all__ = ["search_terms_for_label", "split_and_normalize", "tokens_for_theme"]
