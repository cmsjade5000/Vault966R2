from enum import StrEnum


class MovieMatchSelectionSource(StrEnum):
    OMDB = "omdb"
    TMDB = "tmdb"

    def __str__(self) -> str:
        return str(self.value)
