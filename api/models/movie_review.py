from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base


class MovieReviewCheck(Base):
    __tablename__ = "movie_review_checks"
    __table_args__ = (
        UniqueConstraint(
            "movie_id",
            "issue_type",
            "issue_fingerprint",
            name="uq_movie_review_checks_issue",
        ),
        Index("ix_movie_review_checks_movie_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    issue_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    checked_by_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["MovieReviewCheck"]
