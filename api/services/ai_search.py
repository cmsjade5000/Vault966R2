from __future__ import annotations

import json
import re
from typing import Iterable, List, Optional

import httpx

from api.config import settings
from api.schemas.ai_search import SearchPlan
from api.schemas.llm_filters import ALLOWED_ORDER_BY, LlmMovieFilters
from api.services.llm_filters import normalize_llm_filters
from api.utils.provider_errors import format_provider_error


class AiSearchError(Exception):
    """Raised when the AI search plan pipeline fails."""


class AiSearchProviderUnavailable(AiSearchError):
    """Raised when the AI provider is not configured."""


def _build_prompt(
    query: str,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
) -> list[dict[str, str]]:
    schema = (
        "{"
        '"q": string|null, '
        '"genres": [string], '
        '"moods": [string], '
        '"year_min": int|null, '
        '"year_max": int|null, '
        '"runtime_min": int|null, '
        '"runtime_max": int|null, '
        '"order_by": string'
        "}"
    )
    genre_list = ", ".join(allowed_genres)
    mood_list = ", ".join(allowed_moods)
    system = (
        "You convert natural-language movie search queries into a strict JSON SearchPlan.\n"
        "Rules:\n"
        "- Only output JSON.\n"
        f"- Output must match this schema exactly: {schema}.\n"
        "- Never invent fields.\n"
        "- Use only the provided genres and moods (controlled vocabulary). If unsure, leave lists empty.\n"
        "- Safe defaults: when uncertain, do NOT filter too hard.\n"
        "- Never output SQL or code.\n"
        "Mappings to apply when explicit:\n"
        "- '90s' or '90's' -> year_min=1990, year_max=1999\n"
        "- 'under 90 minutes' or 'less than 90 minutes' -> runtime_max=90\n"
        "- 'family' -> genre includes Family (if available)\n"
        "- 'scary' -> genres include Horror and Thriller (if available; mood 'Scary' if present)\n"
    )
    user = (
        f"Query: {query}\n"
        f"Allowed genres: {genre_list}\n"
        f"Allowed moods: {mood_list}\n"
        f"Allowed order_by: {', '.join(ALLOWED_ORDER_BY)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_llm_json(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiSearchError("LLM response missing choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not content or not isinstance(content, str):
        raise AiSearchError("LLM response missing content")
    return content


def _parse_search_plan(raw_json: str) -> SearchPlan:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AiSearchError("LLM response was not valid JSON") from exc
    return SearchPlan.model_validate(data)


def _summarize_parts(plan: LlmMovieFilters) -> List[str]:
    parts: List[str] = []
    if plan.q:
        parts.append(f"title contains '{plan.q}'")
    if plan.genres:
        parts.append(f"genres: {', '.join(plan.genres)}")
    if plan.moods:
        parts.append(f"moods: {', '.join(plan.moods)}")
    if plan.year_min is not None or plan.year_max is not None:
        start = str(plan.year_min) if plan.year_min is not None else "any"
        end = str(plan.year_max) if plan.year_max is not None else "now"
        parts.append(f"years {start}–{end}")
    if plan.runtime_min is not None or plan.runtime_max is not None:
        if plan.runtime_min is not None and plan.runtime_max is not None:
            parts.append(f"runtime {plan.runtime_min}-{plan.runtime_max} min")
        elif plan.runtime_min is not None:
            parts.append(f"runtime ≥ {plan.runtime_min} min")
        else:
            parts.append(f"runtime ≤ {plan.runtime_max} min")
    if plan.order_by and plan.order_by != "title_asc":
        parts.append(f"sorted by {plan.order_by}")
    return parts


def summarize_search_plan(plan: SearchPlan) -> str:
    parts = _summarize_parts(plan)
    if not parts:
        return "No filters applied; showing all movies."
    explanation = "; ".join(parts)
    if len(explanation) > 200:
        explanation = explanation[:197].rstrip() + "..."
    return explanation


_DECADE_SHORT_MAP = {
    "50s": 1950,
    "60s": 1960,
    "70s": 1970,
    "80s": 1980,
    "90s": 1990,
    "00s": 2000,
    "10s": 2010,
    "20s": 2020,
}
_DECADE_WORDS = {
    "fifties": 1950,
    "sixties": 1960,
    "seventies": 1970,
    "eighties": 1980,
    "nineties": 1990,
    "two thousands": 2000,
    "twenties": 2020,
}
_DECADE_RE = re.compile(r"\b((?:18|19|20)\d)0s\b", re.IGNORECASE)
_SHORT_DECADE_RE = re.compile(r"\b(\d{2})['’]?s\b", re.IGNORECASE)
_RUNTIME_RE = re.compile(
    r"\b(under|less than|<=)\s*(\d{1,3})\s*(minutes|minute|min|mins)\b",
    re.IGNORECASE,
)


def _is_age_phrase(query: str, start_index: int) -> bool:
    window_start = max(0, start_index - 5)
    prefix = query[window_start:start_index]
    return "my " in prefix or "in my" in prefix


def _extract_decades(query: str) -> list[int]:
    hits: list[int] = []
    for match in _DECADE_RE.finditer(query):
        if _is_age_phrase(query, match.start()):
            continue
        try:
            hits.append(int(f"{match.group(1)}0"))
        except ValueError:
            continue
    for match in _SHORT_DECADE_RE.finditer(query):
        if _is_age_phrase(query, match.start()):
            continue
        token = match.group(1)
        key = f"{token}s".lower()
        if key in _DECADE_SHORT_MAP:
            hits.append(_DECADE_SHORT_MAP[key])
    for word, decade in _DECADE_WORDS.items():
        if word in query:
            if f"my {word}" in query or f"in my {word}" in query:
                continue
            hits.append(decade)
    return sorted(set(hits))


def _extract_runtime_max(query: str) -> Optional[int]:
    match = _RUNTIME_RE.search(query)
    if not match:
        return None
    try:
        return int(match.group(2))
    except ValueError:
        return None


def apply_query_normalization(
    plan: SearchPlan,
    *,
    query: str,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
) -> SearchPlan:
    query_lower = query.lower()
    allowed_genres_map = {label.lower(): label for label in allowed_genres}
    allowed_moods_map = {label.lower(): label for label in allowed_moods}

    def _add_genre(name: str) -> None:
        key = name.lower()
        if key in allowed_genres_map and allowed_genres_map[key] not in plan.genres:
            plan.genres.append(allowed_genres_map[key])

    def _add_mood(name: str) -> None:
        key = name.lower()
        if key in allowed_moods_map and allowed_moods_map[key] not in plan.moods:
            plan.moods.append(allowed_moods_map[key])

    if "family" in query_lower or "kids" in query_lower or "kid friendly" in query_lower:
        _add_genre("Family")
        _add_mood("Family")

    if "scary" in query_lower or "spooky" in query_lower or "horror" in query_lower:
        _add_genre("Horror")
        _add_genre("Thriller")
        _add_mood("Scary")

    if "thriller" in query_lower or "thrillers" in query_lower:
        _add_genre("Thriller")

    if (
        "space" in query_lower
        or "sci-fi" in query_lower
        or "sci fi" in query_lower
        or "science fiction" in query_lower
    ):
        _add_genre("Science Fiction")

    decade_hits = _extract_decades(query_lower)
    if decade_hits:
        decade_min = min(decade_hits)
        decade_max = max(decade_hits) + 9
        if plan.year_min is None:
            plan.year_min = decade_min
        else:
            plan.year_min = max(plan.year_min, decade_min)
        if plan.year_max is None:
            plan.year_max = decade_max
        else:
            plan.year_max = min(plan.year_max, decade_max)
        if (
            plan.year_min is not None
            and plan.year_max is not None
            and plan.year_min > plan.year_max
        ):
            plan.year_min = decade_min
            plan.year_max = decade_max

    runtime_max = _extract_runtime_max(query_lower)
    if runtime_max is not None:
        if plan.runtime_max is None:
            plan.runtime_max = runtime_max
        else:
            plan.runtime_max = min(plan.runtime_max, runtime_max)

    return plan


def generate_search_plan(
    query: str,
    *,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
    client: httpx.Client | None = None,
) -> SearchPlan:
    api_key = settings.llm_api_key
    if not api_key:
        raise AiSearchProviderUnavailable("LLM_API_KEY is not configured")

    base_url = settings.llm_base_url.rstrip("/")
    model = settings.llm_model

    payload = {
        "model": model,
        "messages": _build_prompt(query, allowed_genres, allowed_moods),
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    created_client = client is None
    if client is None:
        client = httpx.Client(timeout=15.0)
    provider_error: AiSearchError | None = None
    try:
        response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        raw_json = _extract_llm_json(response.json())
    except httpx.HTTPError as exc:
        provider_error = AiSearchError(format_provider_error("LLM request failed", exc))
    finally:
        if created_client:
            client.close()
    if provider_error is not None:
        raise provider_error from None

    plan = _parse_search_plan(raw_json)
    normalized = normalize_llm_filters(plan, allowed_genres, allowed_moods)
    normalized_plan = SearchPlan.model_validate(normalized.model_dump())
    return apply_query_normalization(
        normalized_plan,
        query=query,
        allowed_genres=allowed_genres,
        allowed_moods=allowed_moods,
    )


__all__ = [
    "AiSearchError",
    "AiSearchProviderUnavailable",
    "generate_search_plan",
    "summarize_search_plan",
]
