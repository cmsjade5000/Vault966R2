"""Model package initializer.
Import key models here so SQLAlchemy registers all mappers at import time.
"""

# Importing these ensures the classes exist when relationships use string names
# like relationship("MovieFlag") inside Movie.
from .movie import Movie, MovieIngestProvenance  # noqa: F401
from .movie_flag import MovieFlag  # noqa: F401

__all__ = ["Movie", "MovieFlag", "MovieIngestProvenance"]
