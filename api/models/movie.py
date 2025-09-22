from typing import Optional

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
