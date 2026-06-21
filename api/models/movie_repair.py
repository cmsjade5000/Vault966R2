from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base


class MovieIdentityRepair(Base):
    __tablename__ = "movie_identity_repairs"
    __table_args__ = (
        Index("ix_movie_identity_repairs_movie_id", "movie_id"),
        Index("ix_movie_identity_repairs_applied_at", "applied_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    applied_by_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    search_title: Mapped[str] = mapped_column(String(300), nullable=False)
    standardized_title: Mapped[str] = mapped_column(String(300), nullable=False)
    selected_title: Mapped[str] = mapped_column(String(300), nullable=False)
    selected_year: Mapped[int | None] = mapped_column(nullable=True)
    selected_imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    selected_tmdb_id: Mapped[int | None] = mapped_column(nullable=True)
    before_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["MovieIdentityRepair"]
