"""Add local usage events.

Revision ID: 202606100007
Revises: 202606100006
Create Date: 2026-06-10 15:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202606100007"
down_revision: Union[str, None] = "202606100006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(length=40), nullable=False),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("page", sa.String(length=20), nullable=False),
        sa.Column("context", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_usage_events_name_created",
        "usage_events",
        ["event_name", "created_at"],
    )
    op.create_index("ix_usage_events_profile_id", "usage_events", ["profile_id"])
    op.create_index("ix_usage_events_movie_id", "usage_events", ["movie_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_movie_id", table_name="usage_events")
    op.drop_index("ix_usage_events_profile_id", table_name="usage_events")
    op.drop_index("ix_usage_events_name_created", table_name="usage_events")
    op.drop_table("usage_events")
