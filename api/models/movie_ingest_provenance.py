from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


class MovieIngestProvenance(Base):
    __tablename__ = "movie_ingest_provenance"
    __table_args__ = (
        UniqueConstraint(
            "movie_id", "provider", name="uq_movie_ingest_provenance_movie_provider"
        ),
        Index("ix_movie_ingest_provenance_movie_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    payload_sha: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    movie = relationship("Movie", back_populates="ingest_provenance")

    def touch(self) -> None:
        """Update the ingested_at timestamp to the current time."""
        self.ingested_at = datetime.now(timezone.utc)
