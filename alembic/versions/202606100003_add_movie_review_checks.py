"""Add persistent human review decisions.

Revision ID: 202606100003
Revises: 202606100002
Create Date: 2026-06-10 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606100003"
down_revision: Union[str, None] = "202606100002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "movie_review_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(length=50), nullable=False),
        sa.Column("issue_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("checked_by_profile_id", sa.Integer(), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["checked_by_profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "movie_id",
            "issue_type",
            "issue_fingerprint",
            name="uq_movie_review_checks_issue",
        ),
    )
    op.create_index(
        "ix_movie_review_checks_movie_id",
        "movie_review_checks",
        ["movie_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_movie_review_checks_movie_id", table_name="movie_review_checks")
    op.drop_table("movie_review_checks")
