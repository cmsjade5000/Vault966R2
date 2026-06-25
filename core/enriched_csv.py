from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


URL_RE = re.compile(r"https?://", re.IGNORECASE)
TMDB_WATCH_RE = re.compile(r"https?://(?:www\.)?themoviedb\.org/movie/\d+[^\\s]*", re.IGNORECASE)


def split_csv_tokens(value: str | None) -> list[str]:
    if not value:
        return []
    raw = str(value)
    parts = re.split(r"[;,]", raw)
    tokens: list[str] = []
    for part in parts:
        token = part.strip()
        if token:
            tokens.append(token)
    return tokens


def join_csv_tokens(tokens: Iterable[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        label = str(token).strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(label)
    return "; ".join(cleaned)


def extract_tmdb_watch_url(tokens: Iterable[str], *, prefer_locale: str = "US") -> str | None:
    urls = [token for token in tokens if TMDB_WATCH_RE.search(token)]
    if not urls:
        return None
    prefer = prefer_locale.upper()
    for url in urls:
        if f"locale={prefer}" in url.upper():
            return url
    return urls[0]


@dataclass(frozen=True)
class WatchProviders:
    region: str
    stream: list[str]
    rent: list[str]
    buy: list[str]
    tmdb_watch_url: str | None = None

    def merged_display(self) -> str:
        return join_csv_tokens(
            [*self.stream, *[f"{x} (rent)" for x in self.rent], *[f"{x} (buy)" for x in self.buy]]
        )


_WATCH_QUALIFIER_RE = re.compile(r"\((rent|buy)\)\s*$", re.IGNORECASE)


def normalize_where_to_watch(
    value: str | None,
    *,
    region: str = "US",
) -> WatchProviders:
    tokens = split_csv_tokens(value)
    tmdb_watch_url = extract_tmdb_watch_url(tokens, prefer_locale=region)

    stream: list[str] = []
    rent: list[str] = []
    buy: list[str] = []

    for token in tokens:
        if URL_RE.search(token):
            continue
        match = _WATCH_QUALIFIER_RE.search(token)
        qualifier = match.group(1).lower() if match else None
        normalized = _WATCH_QUALIFIER_RE.sub("", token).strip()
        if not normalized:
            continue
        if qualifier == "rent":
            rent.append(normalized)
        elif qualifier == "buy":
            buy.append(normalized)
        else:
            stream.append(normalized)

    return WatchProviders(
        region=region.upper(),
        stream=_dedupe_preserve_order(stream),
        rent=_dedupe_preserve_order(rent),
        buy=_dedupe_preserve_order(buy),
        tmdb_watch_url=tmdb_watch_url,
    )


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = str(value).strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


LANGUAGE_NAME_TO_ISO = {
    "english": "en",
    "french": "fr",
    "spanish": "es",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "arabic": "ar",
    "hindi": "hi",
    "japanese": "ja",
    "korean": "ko",
    "mandarin": "zh",
    "chinese": "zh",
    "cantonese": "zh",
    "dutch": "nl",
    "swedish": "sv",
    "norwegian": "no",
    "danish": "da",
    "finnish": "fi",
    "polish": "pl",
    "turkish": "tr",
    "greek": "el",
    "hebrew": "he",
    "thai": "th",
    "vietnamese": "vi",
    "indonesian": "id",
    "malay": "ms",
    "ukrainian": "uk",
    "czech": "cs",
    "slovak": "sk",
    "romanian": "ro",
    "hungarian": "hu",
}

LANGUAGE_ISO_TO_NAME = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "tr": "Turkish",
    "el": "Greek",
    "he": "Hebrew",
    "th": "Thai",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "uk": "Ukrainian",
    "cs": "Czech",
    "sk": "Slovak",
    "ro": "Romanian",
    "hu": "Hungarian",
}

COUNTRY_NAME_TO_ISO = {
    "united states of america": "US",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "great britain": "GB",
    "uk": "GB",
    "south korea": "KR",
    "korea": "KR",
    "north korea": "KP",
    "russia": "RU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "japan": "JP",
    "china": "CN",
    "australia": "AU",
    "canada": "CA",
    "mexico": "MX",
    "brazil": "BR",
    "india": "IN",
}

COUNTRY_ISO_TO_NAME = {
    "US": "United States",
    "GB": "United Kingdom",
    "KR": "South Korea",
    "KP": "North Korea",
    "RU": "Russia",
    "DE": "Germany",
    "FR": "France",
    "IT": "Italy",
    "ES": "Spain",
    "JP": "Japan",
    "CN": "China",
    "AU": "Australia",
    "CA": "Canada",
    "MX": "Mexico",
    "BR": "Brazil",
    "IN": "India",
}

ISO2_RE = re.compile(r"^[A-Za-z]{2}$")


@dataclass(frozen=True)
class NormalizedCodes:
    iso: list[str]
    display: list[str]
    unmapped: list[str]


def normalize_languages(value: str | None) -> NormalizedCodes:
    tokens = split_csv_tokens(value)
    iso: list[str] = []
    display: list[str] = []
    unmapped: list[str] = []

    for token in tokens:
        if ISO2_RE.match(token):
            code = token.lower()
            iso.append(code)
            name = LANGUAGE_ISO_TO_NAME.get(code)
            if name:
                display.append(name)
            continue
        key = token.strip().lower()
        if not key:
            continue
        mapped = LANGUAGE_NAME_TO_ISO.get(key)
        if mapped:
            iso.append(mapped)
            display.append(LANGUAGE_ISO_TO_NAME.get(mapped, token.strip()))
        else:
            display.append(token.strip())
            unmapped.append(token.strip())

    return NormalizedCodes(
        iso=_dedupe_preserve_order(iso),
        display=_dedupe_preserve_order(display),
        unmapped=_dedupe_preserve_order(unmapped),
    )


def normalize_countries(value: str | None) -> NormalizedCodes:
    tokens = split_csv_tokens(value)
    iso: list[str] = []
    display: list[str] = []
    unmapped: list[str] = []

    for token in tokens:
        if ISO2_RE.match(token):
            code = token.upper()
            iso.append(code)
            name = COUNTRY_ISO_TO_NAME.get(code)
            if name:
                display.append(name)
            continue
        key = token.strip().lower()
        if not key:
            continue
        mapped = COUNTRY_NAME_TO_ISO.get(key)
        if mapped:
            iso.append(mapped)
            display.append(COUNTRY_ISO_TO_NAME.get(mapped, token.strip()))
        else:
            display.append(token.strip())
            unmapped.append(token.strip())

    return NormalizedCodes(
        iso=_dedupe_preserve_order(iso),
        display=_dedupe_preserve_order(display),
        unmapped=_dedupe_preserve_order(unmapped),
    )


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def languages_display_from_iso(codes: Iterable[str]) -> list[str]:
    names: list[str] = []
    for code in codes:
        normalized = str(code).strip().lower()
        if not normalized:
            continue
        names.append(LANGUAGE_ISO_TO_NAME.get(normalized, normalized))
    return _dedupe_preserve_order(names)


def countries_display_from_iso(codes: Iterable[str]) -> list[str]:
    names: list[str] = []
    for code in codes:
        normalized = str(code).strip().upper()
        if not normalized:
            continue
        names.append(COUNTRY_ISO_TO_NAME.get(normalized, normalized))
    return _dedupe_preserve_order(names)


__all__ = [
    "NormalizedCodes",
    "WatchProviders",
    "extract_tmdb_watch_url",
    "is_blank",
    "join_csv_tokens",
    "languages_display_from_iso",
    "normalize_countries",
    "normalize_languages",
    "normalize_where_to_watch",
    "countries_display_from_iso",
    "parse_int",
    "parse_iso_date",
    "split_csv_tokens",
]
