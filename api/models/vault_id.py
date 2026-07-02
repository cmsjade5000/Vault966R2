from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base


class RetiredVaultId(Base):
    __tablename__ = "retired_vault_ids"
    __table_args__ = (
        Index("ix_retired_vault_ids_retired_at", "retired_at"),
        Index("ix_retired_vault_ids_source", "source"),
    )

    vault_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    retired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_movie_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_movie_title: Mapped[str | None] = mapped_column(String(300), nullable=True)


__all__ = ["RetiredVaultId"]
