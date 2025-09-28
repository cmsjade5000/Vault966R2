"""Flic scoring, selection, and normalization helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.genres import split_and_normalize
from core.movie_filters import MovieFilterParams


def _normalize_sequence(raw: Optional[Iterable[str]]) -> Tuple[str, ...]:
    """Return a tuple of unique, stripped strings in their original order."""

    if not raw:
        return ()
    seen: list[str] = []
    for value in raw:
        if value is None:
            continue
        candidate = str(value).strip()
        if candidate and candidate not in seen:
            seen.append(candidate)
    return tuple(seen)


@dataclass(frozen=True)
class PickerFilters:
    """Normalized filters used for Flic scoring."""

    genres: Tuple[str, ...] = ()
    moods: Tuple[str, ...] = ()
    runtime_min: Optional[int] = None
    runtime_max: Optional[int] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None

    @classmethod
    def from_params(cls, params: MovieFilterParams) -> "PickerFilters":
        return cls(
            genres=tuple(split_and_normalize(params.genres)),
            moods=params.moods,
            runtime_min=params.runtime_min,
            runtime_max=params.runtime_max,
            year_min=params.year_min,
            year_max=params.year_max,
        )

    @classmethod
    def from_values(
        cls,
        *,
        genres: Optional[Iterable[str]] = None,
        moods: Optional[Iterable[str]] = None,
        runtime_min: Optional[int] = None,
        runtime_max: Optional[int] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
    ) -> "PickerFilters":
        return cls(
            genres=tuple(split_and_normalize(genres or ())),
            moods=_normalize_sequence(moods),
            runtime_min=runtime_min,
            runtime_max=runtime_max,
            year_min=year_min,
            year_max=year_max,
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "genres": list(self.genres),
            "moods": list(self.moods),
            "runtime_min": self.runtime_min,
            "runtime_max": self.runtime_max,
            "year_min": self.year_min,
            "year_max": self.year_max,
        }


@dataclass(frozen=True)
class PickerCandidate:
    """Normalized movie attributes used for Flic scoring."""

    genres: Tuple[str, ...] = ()
    moods: Tuple[str, ...] = ()
    runtime: Optional[int] = None
    year: Optional[int] = None

    @classmethod
    def from_iterables(
        cls,
        *,
        genres: Optional[Iterable[str]] = None,
        moods: Optional[Iterable[str]] = None,
        runtime: Optional[int],
        year: Optional[int],
    ) -> "PickerCandidate":
        return cls(
            genres=tuple(split_and_normalize(genres or ())),
            moods=_normalize_sequence(moods),
            runtime=runtime,
            year=year,
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "genres": list(self.genres),
            "moods": list(self.moods),
            "runtime": self.runtime,
            "year": self.year,
        }


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


__all__ = [
    "PickerCandidate",
    "PickerFilters",
    "calculate_flic_score",
    "pick_movie",
]
