"""Flic scoring and selection logic."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple


def _genre_bonus(candidate: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[float, float]:
    desired = set(filters.get("genres") or [])
    if not desired:
        return 0.0, 0.0
    genres = set(candidate.get("genres") or [])
    if genres & desired:
        return 20.0, 0.0
    return 0.0, -5.0


def _mood_bonus(candidate: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[float, float]:
    desired = set(filters.get("moods") or [])
    if not desired:
        return 0.0, 0.0
    moods = set(candidate.get("moods") or [])
    if moods & desired:
        return 15.0, 0.0
    return 0.0, -5.0


def _runtime_bonus(candidate: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[float, float]:
    runtime_max = filters.get("runtime_max")
    runtime = candidate.get("runtime")
    if not runtime_max or runtime is None:
        return 0.0, 0.0
    diff = runtime_max - runtime
    if diff >= 0:
        return 10.0, 0.0
    penalty = min(abs(diff), 30)
    return 0.0, -penalty


def _year_bonus(candidate: Dict[str, Any], filters: Dict[str, Any]) -> Tuple[float, float]:
    year = candidate.get("year")
    if year is None:
        return 0.0, 0.0
    year_min = filters.get("year_min")
    year_max = filters.get("year_max")
    score = 0.0
    penalty = 0.0
    if year_min and year >= year_min:
        score += 5.0
    elif year_min:
        penalty += min(year_min - year, 20)
    if year_max and year <= year_max:
        score += 5.0
    elif year_max:
        penalty += min(year - year_max, 20)
    return score, -penalty


def calculate_flic_score(
    candidate: Dict[str, Any], filters: Dict[str, Any]
) -> Tuple[float, Dict[str, float]]:
    score = 100.0
    breakdown: Dict[str, float] = {}

    bonus, penalty = _genre_bonus(candidate, filters)
    if bonus:
        breakdown["genre_match"] = bonus
        score += bonus
    if penalty:
        breakdown["genre_miss"] = penalty
        score += penalty

    bonus, penalty = _mood_bonus(candidate, filters)
    if bonus:
        breakdown["mood_match"] = bonus
        score += bonus
    if penalty:
        breakdown["mood_miss"] = penalty
        score += penalty

    bonus, penalty = _runtime_bonus(candidate, filters)
    if bonus:
        breakdown["runtime_match"] = bonus
        score += bonus
    if penalty:
        breakdown["runtime_over"] = penalty
        score += penalty

    bonus, penalty = _year_bonus(candidate, filters)
    if bonus:
        breakdown["year_bonus"] = bonus
        score += bonus
    if penalty:
        breakdown["year_penalty"] = penalty
        score += penalty

    return score, breakdown


def pick_movie(
    candidates: List[Dict[str, Any]], *, filters: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    best: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for candidate in random.sample(candidates, len(candidates)):
        score, breakdown = calculate_flic_score(candidate, filters)
        candidate["flic_score"] = score
        candidate["flic_breakdown"] = breakdown
        if score > best_score:
            best_score = score
            best = candidate
        elif score == best_score and best is not None and random.random() < 0.5:
            best = candidate

    return best
