from enum import Enum


class MovieMatchSelectionSource(str, Enum):
    OMDB = "omdb"
    TMDB = "tmdb"

    def __str__(self) -> str:
        return str(self.value)
