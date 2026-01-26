from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'reviewer'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    preferences = relationship(
        "MoviePreference",
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class MoviePreference(Base):
    __tablename__ = "movie_preferences"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "movie_id",
            name="uq_movie_preferences_profile_movie",
        ),
        Index("ix_movie_preferences_profile_id", "profile_id"),
        Index("ix_movie_preferences_movie_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    liked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    watchlist: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile = relationship("Profile", back_populates="preferences")
