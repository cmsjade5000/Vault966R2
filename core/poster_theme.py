from __future__ import annotations

from typing import Iterable

from core.genres import tokens_for_theme

DEFAULT_THEME = "poster-theme-default"

THEME_PRIORITY_MAP = {
    "horror": ("poster-theme-horror", 100),
    "thriller": ("poster-theme-horror", 90),
    "mystery": ("poster-theme-noir", 75),
    "crime": ("poster-theme-noir", 70),
    "film-noir": ("poster-theme-noir", 80),
    "animation": ("poster-theme-bright", 95),
    "family": ("poster-theme-bright", 85),
    "children": ("poster-theme-bright", 85),
    "kids": ("poster-theme-bright", 85),
    "comedy": ("poster-theme-bright", 70),
    "adventure": ("poster-theme-adventure", 80),
    "action": ("poster-theme-adventure", 75),
    "fantasy": ("poster-theme-fantasy", 90),
    "science fiction": ("poster-theme-sci-fi", 95),
    "sci-fi": ("poster-theme-sci-fi", 95),
    "romance": ("poster-theme-romance", 85),
    "drama": ("poster-theme-drama", 60),
    "biography": ("poster-theme-documentary", 55),
    "documentary": ("poster-theme-documentary", 65),
    "history": ("poster-theme-documentary", 60),
    "music": ("poster-theme-bright", 60),
    "musical": ("poster-theme-bright", 65),
    "sport": ("poster-theme-adventure", 65),
    "war": ("poster-theme-war", 80),
    "western": ("poster-theme-western", 75),
    "biopic": ("poster-theme-documentary", 55),
    "historical": ("poster-theme-documentary", 55),
    "superhero": ("poster-theme-adventure", 85),
}


def select_poster_theme(genres: Iterable[str] | None) -> str:
    best_theme = DEFAULT_THEME
    best_priority = -1

    if not genres:
        return best_theme

    for token in tokens_for_theme(genres):
        if token in THEME_PRIORITY_MAP:
            theme, priority = THEME_PRIORITY_MAP[token]
            if priority > best_priority:
                best_theme = theme
                best_priority = priority

    return best_theme
