"""add movie flag reporter

Revision ID: 202606180001
Revises: 202606100008
Create Date: 2026-06-18 01:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202606180001"
down_revision: Union[str, None] = "202606100008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("movie_flags") as batch_op:
        batch_op.add_column(sa.Column("reported_by_profile_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_movie_flags_reported_by_profile_id_profiles",
            "profiles",
            ["reported_by_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("movie_flags") as batch_op:
        batch_op.drop_constraint(
            "fk_movie_flags_reported_by_profile_id_profiles",
            type_="foreignkey",
        )
        batch_op.drop_column("reported_by_profile_id")
