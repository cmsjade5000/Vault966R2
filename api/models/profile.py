from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class AppSetup(Base):
    __tablename__ = "app_setup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    owner_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


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
    credential = relationship(
        "ProfileCredential",
        back_populates="profile",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ProfileCredential(Base):
    __tablename__ = "profile_credentials"
    __table_args__ = (UniqueConstraint("profile_id", name="uq_profile_credentials_profile_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    access_key_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    access_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    passcode_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    passcode_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    kdf_name: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default=text("'pbkdf2_sha256'")
    )
    kdf_iterations: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("200000")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    profile = relationship("Profile", back_populates="credential")


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
