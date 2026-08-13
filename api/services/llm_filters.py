from __future__ import annotations

import json
from typing import Iterable, List

import httpx

from api.config import settings
from api.schemas.llm_filters import ALLOWED_ORDER_BY, LlmMovieFilters
from api.utils.provider_errors import format_provider_error
from core.genres import split_and_normalize


class LlmFilterError(Exception):
    """Raised when the LLM filter pipeline fails."""


class LlmProviderUnavailable(LlmFilterError):
    """Raised when the LLM provider is not configured."""


def _dedupe(items: Iterable[str]) -> List[str]:
    seen: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def normalize_llm_filters(
    filters: LlmMovieFilters,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
) -> LlmMovieFilters:
    genre_map: dict[str, str] = {}
    for label in allowed_genres:
        lowered = label.lower()
        genre_map[lowered] = label
        for alias in split_and_normalize([label]):
            genre_map[alias.lower()] = label
    mood_map = {label.lower(): label for label in allowed_moods}

    normalized_genres: List[str] = []
    for label in split_and_normalize(filters.genres):
        key = label.lower()
        if key in genre_map:
            normalized_genres.append(genre_map[key])

    normalized_moods: List[str] = []
    for label in filters.moods:
        key = label.strip().lower()
        if key in mood_map:
            normalized_moods.append(mood_map[key])

    filters.genres = _dedupe(normalized_genres)
    filters.moods = _dedupe(normalized_moods)
    return filters


def _build_prompt(
    query: str,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
) -> list[dict[str, str]]:
    genre_list = ", ".join(allowed_genres)
    mood_list = ", ".join(allowed_moods)
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
    system = (
        "You convert natural-language movie queries into structured filters. "
        "Output ONLY JSON that matches this schema exactly: "
        f"{schema}. "
        "Use only the provided genres and moods. If a value is unknown, "
        "leave the list empty or use null. "
        "Never output SQL, code, or explanations."
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
        raise LlmFilterError("LLM response missing choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not content or not isinstance(content, str):
        raise LlmFilterError("LLM response missing content")
    return content


def _parse_llm_filters(raw_json: str) -> LlmMovieFilters:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise LlmFilterError("LLM response was not valid JSON") from exc
    return LlmMovieFilters.model_validate(data)


def generate_llm_filters(
    query: str,
    *,
    allowed_genres: Iterable[str],
    allowed_moods: Iterable[str],
    client: httpx.Client | None = None,
) -> LlmMovieFilters:
    api_key = settings.llm_api_key
    if not api_key:
        raise LlmProviderUnavailable("LLM_API_KEY is not configured")

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
    provider_error: LlmFilterError | None = None
    try:
        response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        raw_json = _extract_llm_json(response.json())
    except httpx.HTTPError as exc:
        provider_error = LlmFilterError(format_provider_error("LLM request failed", exc))
    finally:
        if created_client:
            client.close()
    if provider_error is not None:
        raise provider_error from None

    filters = _parse_llm_filters(raw_json)
    return normalize_llm_filters(filters, allowed_genres, allowed_moods)


__all__ = [
    "LlmFilterError",
    "LlmProviderUnavailable",
    "generate_llm_filters",
    "normalize_llm_filters",
]
