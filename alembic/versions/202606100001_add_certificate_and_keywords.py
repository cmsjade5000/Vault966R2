"""Add certificate and keywords to movies.

Revision ID: 202606100001
Revises: 202601250002
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606100001"
down_revision: Union[str, None] = "202601250002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("movies") as batch_op:
        batch_op.add_column(sa.Column("certificate", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("keywords", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("movies") as batch_op:
        batch_op.drop_column("keywords")
        batch_op.drop_column("certificate")
