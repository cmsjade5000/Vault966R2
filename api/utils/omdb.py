from __future__ import annotations

import re
from typing import Any


VOTES_RE = re.compile(r"[,\s]")


def parse_imdb_rating(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    try:
        rating = float(text)
    except ValueError:
        return None
    if rating < 0 or rating > 10:
        return None
    return rating


def parse_imdb_votes(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    cleaned = VOTES_RE.sub("", text)
    if not cleaned.isdigit():
        return None
    votes = int(cleaned)
    return votes if votes >= 0 else None


def parse_rt_score(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "N/A":
        return None
    if text.endswith("%"):
        try:
            score = int(round(float(text[:-1])))
        except ValueError:
            return None
        return score if 0 <= score <= 100 else None
    if "/" in text:
        left, right = text.split("/", 1)
        try:
            numerator = float(left.strip())
            denominator = float(right.strip())
        except ValueError:
            return None
        if denominator <= 0:
            return None
        score = int(round((numerator / denominator) * 100))
        return score if 0 <= score <= 100 else None
    return None


def extract_rotten_tomatoes_score(omdb_payload: dict | None) -> int | None:
    if not omdb_payload:
        return None
    ratings = omdb_payload.get("Ratings")
    if not isinstance(ratings, list):
        return None
    for entry in ratings:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("Source") or "").strip().lower()
        if source != "rotten tomatoes":
            continue
        return parse_rt_score(entry.get("Value"))
    return None


__all__ = [
    "extract_rotten_tomatoes_score",
    "parse_imdb_rating",
    "parse_imdb_votes",
    "parse_rt_score",
]
