from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class SourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (Index("ix_source_snapshots_status_uploaded", "status", "uploaded_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    raw_csv: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    uploaded_by_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows = relationship(
        "SourceMovieRow",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SourceMovieRow.row_number",
    )


class SourceMovieRow(Base):
    __tablename__ = "source_movie_rows"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "row_number", name="uq_source_movie_rows_snapshot_row"),
        Index("ix_source_movie_rows_snapshot_id", "snapshot_id"),
        Index("ix_source_movie_rows_normalized_title", "normalized_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(300), nullable=False)
    runtime: Mapped[int | None] = mapped_column(Integer, nullable=True)
    director: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_directors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content_rating: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hd: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duplicate_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    snapshot = relationship("SourceSnapshot", back_populates="rows")
    match = relationship(
        "SourceReconciliationMatch",
        back_populates="source_row",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SourceReconciliationMatch(Base):
    __tablename__ = "source_reconciliation_matches"
    __table_args__ = (
        UniqueConstraint("source_row_id", name="uq_source_reconciliation_matches_row"),
        Index("ix_source_reconciliation_matches_movie_id", "movie_id"),
        Index("ix_source_reconciliation_matches_type", "match_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_row_id: Mapped[int] = mapped_column(
        ForeignKey("source_movie_rows.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int | None] = mapped_column(
        ForeignKey("movies.id", ondelete="SET NULL"), nullable=True
    )
    match_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_movie_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_row = relationship("SourceMovieRow", back_populates="match")
    movie = relationship("Movie")


class SourceFieldDecision(Base):
    __tablename__ = "source_field_decisions"
    __table_args__ = (
        Index("ix_source_field_decisions_row_field", "source_row_id", "field_name"),
        Index("ix_source_field_decisions_movie_id", "movie_id"),
        Index("ix_source_field_decisions_decision", "decision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_row_id: Mapped[int] = mapped_column(
        ForeignKey("source_movie_rows.id", ondelete="CASCADE"), nullable=False
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(30), nullable=False)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    decided_by_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    undone_by_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source_row = relationship("SourceMovieRow")
    movie = relationship("Movie")


class OwnedMovieCopy(Base):
    __tablename__ = "owned_movie_copies"
    __table_args__ = (
        UniqueConstraint("source_row_id", name="uq_owned_movie_copies_source_row"),
        Index("ix_owned_movie_copies_movie_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_row_id: Mapped[int] = mapped_column(
        ForeignKey("source_movie_rows.id", ondelete="CASCADE"), nullable=False
    )
    hd: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    movie = relationship("Movie")
    snapshot = relationship("SourceSnapshot")
    source_row = relationship("SourceMovieRow")


__all__ = [
    "OwnedMovieCopy",
    "SourceFieldDecision",
    "SourceMovieRow",
    "SourceReconciliationMatch",
    "SourceSnapshot",
]
