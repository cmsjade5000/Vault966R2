"""merge semantic search head

Revision ID: b8617525ce13
Revises: 202503081215, b6f42a2b7d2a
Create Date: 2025-12-31 01:13:42.603555

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "b8617525ce13"
down_revision: Union[str, None] = ("202503081215", "b6f42a2b7d2a")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
