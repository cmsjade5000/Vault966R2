"""Drop tagline, revenue, and budget from movies.

Revision ID: b6f42a2b7d2a
Revises: 9ab64fd9beb0
Create Date: 2025-03-03 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b6f42a2b7d2a"
down_revision: Union[str, None] = "9ab64fd9beb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("movies")}
    with op.batch_alter_table("movies") as batch_op:
        if "tagline" in existing:
            batch_op.drop_column("tagline")
        if "revenue" in existing:
            batch_op.drop_column("revenue")
        if "budget" in existing:
            batch_op.drop_column("budget")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("movies")}
    with op.batch_alter_table("movies") as batch_op:
        if "tagline" not in existing:
            batch_op.add_column(sa.Column("tagline", sa.String(length=500), nullable=True))
        if "revenue" not in existing:
            batch_op.add_column(sa.Column("revenue", sa.BigInteger(), nullable=True))
        if "budget" not in existing:
            batch_op.add_column(sa.Column("budget", sa.BigInteger(), nullable=True))
