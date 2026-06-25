"""Merge heads

Revision ID: c453b689bb5c
Revises: 202410101206, 82242007879d
Create Date: 2025-09-28 19:05:11.997133

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "c453b689bb5c"
down_revision: Union[str, None] = ("202410101206", "82242007879d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
