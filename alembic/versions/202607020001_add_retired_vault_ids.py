"""add retired vault id registry

Revision ID: 202607020001
Revises: 202606270001
Create Date: 2026-07-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202607020001"
down_revision: Union[str, None] = "202606270001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_RETIRED_VAULT_IDS = (
    "V0087",
    "V0135",
    "V0288",
    "V0309",
    "V0539",
    "V0584",
    "V0631",
    "V0637",
    "V0643",
    "V0695",
    "V0942",
)


def upgrade() -> None:
    op.create_table(
        "retired_vault_ids",
        sa.Column("vault_id", sa.String(length=20), nullable=False),
        sa.Column(
            "retired_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("deleted_movie_id", sa.Integer(), nullable=True),
        sa.Column("deleted_movie_title", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("vault_id"),
    )
    op.create_index(
        "ix_retired_vault_ids_retired_at",
        "retired_vault_ids",
        ["retired_at"],
        unique=False,
    )
    op.create_index(
        "ix_retired_vault_ids_source",
        "retired_vault_ids",
        ["source"],
        unique=False,
    )
    retired_table = sa.table(
        "retired_vault_ids",
        sa.column("vault_id", sa.String),
        sa.column("source", sa.String),
        sa.column("reason", sa.Text),
    )
    op.bulk_insert(
        retired_table,
        [
            {
                "vault_id": vault_id,
                "source": "legacy_gap",
                "reason": "Known legacy Vault ID gap reserved to prevent reuse.",
            }
            for vault_id in LEGACY_RETIRED_VAULT_IDS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_retired_vault_ids_source", table_name="retired_vault_ids")
    op.drop_index("ix_retired_vault_ids_retired_at", table_name="retired_vault_ids")
    op.drop_table("retired_vault_ids")
