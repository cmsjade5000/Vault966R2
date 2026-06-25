from __future__ import annotations

import re

SPACE_RE = re.compile(r"\s+")
TRAILING_YEAR_RE = re.compile(r"\s*\((?:18|19|20)\d{2}\)\s*$")
TRAILING_EDITION_RE = re.compile(
    r"""
    \s*
    (?:
        \(
            (?=[^)]*
                (?:
                    unrated
                    |extended(?:\s+(?:edition|cut|version))?
                    |director'?s\s+cut
                    |special\s+edition
                    |theatrical\s+(?:cut|version)
                    |restored\s+edition
                    |remastered
                    |anniversary\s+edition
                    |collector'?s\s+edition
                    |ultimate\s+edition
                )
            )
            [^)]*
        \)
        |
        [-–—:]\s*
        (?:
            unrated
            |extended(?:\s+(?:edition|cut|version))?
            |director'?s\s+cut
            |special\s+edition
            |theatrical\s+(?:cut|version)
            |restored\s+edition
            |remastered
            |anniversary\s+edition
            |collector'?s\s+edition
            |ultimate\s+edition
        )
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def display_movie_title(value: object) -> str:
    """Return a cleaner UI label without changing the canonical movie title."""
    title = SPACE_RE.sub(" ", str(value or "")).strip()
    if not title:
        return ""

    previous = None
    while title and title != previous:
        previous = title
        title = TRAILING_YEAR_RE.sub("", title)
        title = TRAILING_EDITION_RE.sub("", title)
        title = SPACE_RE.sub(" ", title).strip()
    return title or SPACE_RE.sub(" ", str(value or "")).strip()


__all__ = ["display_movie_title"]
