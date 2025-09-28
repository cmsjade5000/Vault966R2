"""add flic memory table

Revision ID: 202410101203
Revises: 202410101202
Create Date: 2024-10-10 12:03:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "202410101203"
down_revision: Union[str, None] = "202410101202"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create flic_memory only if missing."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("flic_memory"):
        op.create_table(
            "flic_memory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("movie_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        )


def downgrade() -> None:
    """Drop flic_memory only if it exists."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("flic_memory"):
        op.drop_table("flic_memory")
