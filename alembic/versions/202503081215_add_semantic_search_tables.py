"""Add semantic search tables.

Revision ID: 202503081215
Revises: c453b689bb5c
Create Date: 2025-03-08 12:15:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "202503081215"
down_revision: Union[str, None] = "c453b689bb5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "movie_documents",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("doc_version", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("movie_id"),
    )
    op.create_index("ix_movie_documents_movie_id", "movie_documents", ["movie_id"], unique=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_movie_documents_embedding "
        "ON movie_documents USING ivfflat (embedding vector_l2_ops)"
    )

    op.create_table(
        "ai_cache",
        sa.Column("cache_key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_index("ix_ai_cache_expires_at", "ai_cache", ["expires_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.drop_index("ix_ai_cache_expires_at", table_name="ai_cache")
    op.drop_table("ai_cache")
    op.execute("DROP INDEX IF EXISTS ix_movie_documents_embedding")
    op.drop_index("ix_movie_documents_movie_id", table_name="movie_documents")
    op.drop_table("movie_documents")
