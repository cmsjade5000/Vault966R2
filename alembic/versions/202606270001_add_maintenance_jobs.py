"""add maintenance job history

Revision ID: 202606270001
Revises: 202606210001
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202606270001"
down_revision: Union[str, None] = "202606210001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "maintenance_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("task_id", sa.String(length=40), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("started_by_profile_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("reports", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["started_by_profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_maintenance_jobs_run_id",
        "maintenance_jobs",
        ["run_id"],
        unique=True,
    )
    op.create_index(
        "ix_maintenance_jobs_task_started",
        "maintenance_jobs",
        ["task_id", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_jobs_state",
        "maintenance_jobs",
        ["state"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_maintenance_jobs_state", table_name="maintenance_jobs")
    op.drop_index("ix_maintenance_jobs_task_started", table_name="maintenance_jobs")
    op.drop_index("ix_maintenance_jobs_run_id", table_name="maintenance_jobs")
    op.drop_table("maintenance_jobs")
