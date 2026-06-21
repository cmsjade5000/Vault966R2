"""add movie identity repair history

Revision ID: 202606210001
Revises: 202606180001
Create Date: 2026-06-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606210001"
down_revision: Union[str, None] = "202606180001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "movie_identity_repairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("applied_by_profile_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("search_title", sa.String(length=300), nullable=False),
        sa.Column("standardized_title", sa.String(length=300), nullable=False),
        sa.Column("selected_title", sa.String(length=300), nullable=False),
        sa.Column("selected_year", sa.Integer(), nullable=True),
        sa.Column("selected_imdb_id", sa.String(length=20), nullable=True),
        sa.Column("selected_tmdb_id", sa.Integer(), nullable=True),
        sa.Column("before_values", sa.JSON(), nullable=True),
        sa.Column("after_values", sa.JSON(), nullable=True),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["applied_by_profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_movie_identity_repairs_movie_id",
        "movie_identity_repairs",
        ["movie_id"],
        unique=False,
    )
    op.create_index(
        "ix_movie_identity_repairs_applied_at",
        "movie_identity_repairs",
        ["applied_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_movie_identity_repairs_applied_at", table_name="movie_identity_repairs")
    op.drop_index("ix_movie_identity_repairs_movie_id", table_name="movie_identity_repairs")
    op.drop_table("movie_identity_repairs")
