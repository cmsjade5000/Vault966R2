"""Preserve every source field decision as audit history.

Revision ID: 202606100005
Revises: 202606100004
Create Date: 2026-06-10 03:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202606100005"
down_revision: Union[str, None] = "202606100004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("source_field_decisions") as batch_op:
        batch_op.drop_constraint(
            "uq_source_field_decisions_field",
            type_="unique",
        )
        batch_op.create_index(
            "ix_source_field_decisions_row_field",
            ["source_row_id", "field_name"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("source_field_decisions") as batch_op:
        batch_op.drop_index("ix_source_field_decisions_row_field")
        batch_op.create_unique_constraint(
            "uq_source_field_decisions_field",
            ["source_row_id", "field_name"],
        )
