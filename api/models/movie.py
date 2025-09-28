from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from api.models.movie_flag import MovieFlag

from api.db import Base

# Association tables
movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

movie_moods = Table(
    "movie_moods",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("mood_id", ForeignKey("moods.id", ondelete="CASCADE"), primary_key=True),
)


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    runtime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # minutes
    plot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    imdb_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imdb_votes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rt_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    where_to_watch: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    languages: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    countries: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    poster_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    backdrop_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")
    moods = relationship("Mood", secondary=movie_moods, back_populates="movies")
    roles = relationship("Role", back_populates="movie", cascade="all, delete-orphan")
    flag: Mapped[Optional["MovieFlag"]] = relationship(
        "MovieFlag",
        back_populates="movie",
        cascade="all, delete-orphan",
        uselist=False,
    )
    ingest_provenance: Mapped[Optional["MovieIngestProvenance"]] = relationship(
        "MovieIngestProvenance",
        back_populates="movie",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    movies = relationship("Movie", secondary=movie_genres, back_populates="genres")


class Mood(Base):
    __tablename__ = "moods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    emoji: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    movies = relationship("Movie", secondary=movie_moods, back_populates="moods")


class MovieIngestProvenance(Base):
    __tablename__ = "movie_ingest_provenance"

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    movie = relationship("Movie", back_populates="ingest_provenance")
