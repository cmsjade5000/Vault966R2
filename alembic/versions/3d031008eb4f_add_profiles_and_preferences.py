"""add profiles and preferences

Revision ID: 3d031008eb4f
Revises: b8617525ce13
Create Date: 2026-01-01 21:55:46.340261

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d031008eb4f"
down_revision: Union[str, None] = "b8617525ce13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "movie_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "liked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "watchlist",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "profile_id",
            "movie_id",
            name="uq_movie_preferences_profile_movie",
        ),
    )
    op.create_index(
        "ix_movie_preferences_profile_id",
        "movie_preferences",
        ["profile_id"],
    )
    op.create_index(
        "ix_movie_preferences_movie_id",
        "movie_preferences",
        ["movie_id"],
    )

    profiles_table = sa.table(
        "profiles",
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        profiles_table,
        [{"name": "User A"}, {"name": "User B"}],
    )


def downgrade() -> None:
    op.drop_index("ix_movie_preferences_movie_id", table_name="movie_preferences")
    op.drop_index("ix_movie_preferences_profile_id", table_name="movie_preferences")
    op.drop_table("movie_preferences")
    op.drop_table("profiles")
