"""add profile roles

Revision ID: 202601250002
Revises: 3d031008eb4f
Create Date: 2026-01-25 22:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202601250002"
down_revision: Union[str, None] = "3d031008eb4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'reviewer'"),
        ),
    )
    op.execute("UPDATE profiles SET role = 'admin' WHERE name = 'User A'")
    op.execute("UPDATE profiles SET role = 'reviewer' WHERE role IS NULL OR role = ''")


def downgrade() -> None:
    op.drop_column("profiles", "role")
