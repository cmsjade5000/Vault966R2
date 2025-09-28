"""add flic memory table

Revision ID: 202410101203
Revises: 202410101202
Create Date: 2024-10-10 12:50:00

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
    op.create_table(
        "flic_memory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("flic_memory")
