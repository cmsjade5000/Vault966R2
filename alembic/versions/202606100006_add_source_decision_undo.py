"""Add reversible source-review decisions.

Revision ID: 202606100006
Revises: 202606100005
Create Date: 2026-06-10 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202606100006"
down_revision: Union[str, None] = "202606100005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("source_field_decisions") as batch_op:
        batch_op.add_column(sa.Column("undone_by_profile_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_source_field_decisions_undone_by_profile",
            "profiles",
            ["undone_by_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("source_field_decisions") as batch_op:
        batch_op.drop_constraint(
            "fk_source_field_decisions_undone_by_profile",
            type_="foreignkey",
        )
        batch_op.drop_column("undone_at")
        batch_op.drop_column("undone_by_profile_id")
