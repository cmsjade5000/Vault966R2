from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from api.models.movie_flag import MovieFlag
    from api.models.semantic_search import MovieDocument

from api.db import Base
from api.db_types import LenientJSONText

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

movie_cast = Table(
    "movie_cast",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
    Column("character", String(300), nullable=True),
    Column("order_index", Integer, nullable=True),
    Index("ix_movie_cast_movie_id", "movie_id"),
)

movie_crew = Table(
    "movie_crew",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("person_id", ForeignKey("people.id", ondelete="CASCADE"), primary_key=True),
    Column("department", String(200), nullable=True),
    Column("job", String(200), nullable=True),
    Index("ix_movie_crew_movie_id", "movie_id"),
)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        Index("ix_movies_imdb_id", "imdb_id", unique=True),
        Index("ix_movies_tmdb_id", "tmdb_id", unique=True),
        CheckConstraint("imdb_rating BETWEEN 0 AND 10", name="ck_movies_imdb_rating_range"),
        CheckConstraint("metascore BETWEEN 0 AND 100", name="ck_movies_metascore_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    vault_id: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    runtime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # minutes
    plot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    awards: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    certificate: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    keywords: Mapped[Optional[object]] = mapped_column(JSON, nullable=True)

    imdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    imdb_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imdb_votes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metascore: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tomato_meter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tomato_audience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rt_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    last_tmdb_fetch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_omdb_fetch_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tmdb_etag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tmdb_payload_sha: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    omdb_payload_sha: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Postgres stores these as JSONB (see Alembic migration). SQLite dumps in the repo
    # store raw TEXT, so keep SQLite lenient to avoid JSON decode issues.
    _lenient_json = JSON().with_variant(LenientJSONText(), "sqlite")
    where_to_watch: Mapped[Optional[object]] = mapped_column(_lenient_json, nullable=True)
    languages: Mapped[Optional[object]] = mapped_column(_lenient_json, nullable=True)
    countries: Mapped[Optional[object]] = mapped_column(_lenient_json, nullable=True)
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
    ingest_provenance: Mapped[List["MovieIngestProvenance"]] = relationship(
        "MovieIngestProvenance",
        back_populates="movie",
        cascade="all, delete-orphan",
    )
    document: Mapped[Optional["MovieDocument"]] = relationship(
        "MovieDocument",
        back_populates="movie",
        cascade="all, delete-orphan",
        uselist=False,
    )


class MovieIngestProvenance(Base):
    __tablename__ = "movie_ingest_provenance"
    __table_args__ = (
        Index("ix_movie_ingest_provenance_movie_id", "movie_id"),
        UniqueConstraint(
            "movie_id",
            "provider",
            name="uq_movie_ingest_provenance_movie_provider",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload_sha: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    movie: Mapped["Movie"] = relationship(
        "Movie",
        back_populates="ingest_provenance",
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
