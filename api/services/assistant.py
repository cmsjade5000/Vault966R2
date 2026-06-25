from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import httpx

from api.config import settings


class AssistantError(Exception):
    """Raised when the assistant response pipeline fails."""


class AssistantProviderUnavailable(AssistantError):
    """Raised when the LLM provider is not configured."""


@dataclass(frozen=True)
class AssistantTemplate:
    template: str
    pick_count: int
    followup: str


def _build_prompt(query: str, movies: Iterable[dict]) -> list[dict[str, str]]:
    catalog = json.dumps(list(movies), ensure_ascii=True)
    system = (
        "You are a private vault movie concierge. "
        "Respond in short, voice-friendly copy. "
        "Output ONLY JSON with keys: template, pick_count, followup. "
        "Rules:\n"
        "- template must contain only placeholders {{movie_1}}, {{movie_2}}, {{movie_3}} "
        "  instead of real movie titles.\n"
        "- pick_count must be an integer between 1 and 3.\n"
        "- followup is optional; use an empty string if not needed.\n"
        "- Keep template under 40 words, no markdown, no quotes.\n"
        "- Do not repeat the user's query verbatim."
    )
    user = f"Query: {query}\nCatalog: {catalog}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_llm_json(payload: dict) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AssistantError("LLM response missing choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if not content or not isinstance(content, str):
        raise AssistantError("LLM response missing content")
    return content


def _parse_template(raw_json: str) -> AssistantTemplate:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AssistantError("LLM response was not valid JSON") from exc

    template = str(data.get("template", "")).strip()
    followup = str(data.get("followup", "")).strip()
    try:
        pick_count = int(data.get("pick_count", 2))
    except (TypeError, ValueError):
        pick_count = 2

    pick_count = max(1, min(pick_count, 3))
    if "{{movie_1}}" not in template:
        template = "Try {{movie_1}} for a secure vault pick."
        pick_count = 1
    return AssistantTemplate(template=template, pick_count=pick_count, followup=followup)


def generate_assistant_template(
    query: str,
    *,
    movies: Iterable[dict],
    client: httpx.Client | None = None,
) -> AssistantTemplate:
    api_key = settings.llm_api_key
    if not api_key:
        raise AssistantProviderUnavailable("LLM_API_KEY is not configured")

    base_url = settings.llm_base_url.rstrip("/")
    model = settings.llm_model

    payload = {
        "model": model,
        "messages": _build_prompt(query, movies),
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    created_client = client is None
    if client is None:
        client = httpx.Client(timeout=15.0)
    try:
        response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        raw_json = _extract_llm_json(response.json())
    except httpx.HTTPError as exc:
        raise AssistantError(f"LLM request failed: {exc}") from exc
    finally:
        if created_client:
            client.close()

    return _parse_template(raw_json)


__all__ = [
    "AssistantError",
    "AssistantProviderUnavailable",
    "AssistantTemplate",
    "generate_assistant_template",
]
