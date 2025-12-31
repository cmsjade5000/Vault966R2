from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.config import settings
from api.db import Base


class MovieDocument(Base):
    __tablename__ = "movie_documents"
    __table_args__ = (
        Index("ix_movie_documents_movie_id", "movie_id"),
        Index("ix_movie_documents_embedding", "embedding", postgresql_using="ivfflat"),
    )

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    doc_version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[object] = mapped_column(
        Vector(settings.llm_embedding_dim).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    movie = relationship("Movie", back_populates="document")


class AiCache(Base):
    __tablename__ = "ai_cache"
    __table_args__ = (Index("ix_ai_cache_expires_at", "expires_at"),)

    cache_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[object] = mapped_column(JSON(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
