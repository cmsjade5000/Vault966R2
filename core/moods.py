from __future__ import annotations

"""Deterministic mood taxonomy and scoring helpers."""

from typing import Iterable, List

from core.genres import split_and_normalize

MOOD_TAXONOMY: dict[str, dict[str, str]] = {
    "High-octane": {
        "description": "Fast-paced, adrenaline-forward stories.",
    },
    "Atmospheric": {
        "description": "Moody, immersive, tense, or eerie.",
    },
    "Gritty": {
        "description": "Hard-edged, raw, and grounded.",
    },
    "Heartfelt": {
        "description": "Warm, emotional, relationship-driven.",
    },
    "Thoughtful": {
        "description": "Reflective, character-driven, thematic.",
    },
}

MOOD_RULES: dict[str, dict[str, set[str]]] = {
    "High-octane": {
        "strong": {"action", "adventure", "war"},
        "soft": {"thriller", "science fiction"},
    },
    "Atmospheric": {
        "strong": {"horror", "mystery", "thriller"},
        "soft": {"fantasy", "science fiction"},
    },
    "Gritty": {
        "strong": {"crime", "war", "western"},
        "soft": {"thriller", "drama"},
    },
    "Heartfelt": {
        "strong": {"romance", "family", "animation", "music"},
        "soft": {"comedy", "drama"},
    },
    "Thoughtful": {
        "strong": {"drama", "history", "documentary"},
        "soft": {"mystery", "science fiction"},
    },
}


def _normalize_genres(raw: Iterable[str]) -> List[str]:
    return [label.lower() for label in split_and_normalize(raw)]


def score_moods(
    genres: Iterable[str],
    *,
    max_moods: int = 1,
    min_score: int = 1,
) -> List[str]:
    tokens = _normalize_genres(genres)
    if not tokens:
        return []
    scores = {mood: 0 for mood in MOOD_RULES}
    for token in tokens:
        for mood, rule in MOOD_RULES.items():
            if token in rule["strong"]:
                scores[mood] += 2
            elif token in rule["soft"]:
                scores[mood] += 1
    ranked = [(mood, score) for mood, score in scores.items() if score >= min_score]
    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [mood for mood, _ in ranked[:max_moods]]


__all__ = ["MOOD_RULES", "MOOD_TAXONOMY", "score_moods"]
