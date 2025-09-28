"""Add indexes and person constraint

Revision ID: 202410101201
Revises: 202410101200
Create Date: 2024-10-10 12:00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "202410101201"
down_revision: Union[str, None] = "202410101200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_people_name_tmdb_id", "people", ["name", "tmdb_id"])
    op.create_index("ix_movies_year", "movies", ["year"], unique=False)
    op.create_index("ix_roles_role_type_movie_id", "roles", ["role_type", "movie_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roles_role_type_movie_id", table_name="roles")
    op.drop_index("ix_movies_year", table_name="movies")
    op.drop_constraint("uq_people_name_tmdb_id", "people", type_="unique")
