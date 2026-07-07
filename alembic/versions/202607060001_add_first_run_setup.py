"""add first run setup

Revision ID: 202607060001
Revises: 202607020001
Create Date: 2026-07-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607060001"
down_revision: Union[str, None] = "202607020001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_setup",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "owner_profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    )
    op.create_table(
        "profile_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_key_salt", sa.String(length=64), nullable=False),
        sa.Column("access_key_hash", sa.String(length=128), nullable=False),
        sa.Column("passcode_salt", sa.String(length=64), nullable=False),
        sa.Column("passcode_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "kdf_name",
            sa.String(length=40),
            server_default=sa.text("'pbkdf2_sha256'"),
            nullable=False,
        ),
        sa.Column("kdf_iterations", sa.Integer(), server_default=sa.text("200000"), nullable=False),
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
        sa.UniqueConstraint("profile_id", name="uq_profile_credentials_profile_id"),
    )


def downgrade() -> None:
    op.drop_table("profile_credentials")
    op.drop_table("app_setup")
