"""Add indexes and person constraint

Revision ID: 202410101201
Revises: ca876fb0a006
Create Date: 2024-10-10 12:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202410101201"
down_revision: Union[str, None] = "ca876fb0a006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {ix["name"] for ix in inspector.get_indexes("people")}
    existing_constraints = {ck["name"] for ck in inspector.get_unique_constraints("people")}

    if bind.dialect.name == "sqlite":
        if "uq_people_name_tmdb_id" not in existing_indexes:
            op.create_index(
                "uq_people_name_tmdb_id",
                "people",
                ["name", "tmdb_id"],
                unique=True,
            )
    else:
        if "uq_people_name_tmdb_id" not in existing_constraints:
            op.create_unique_constraint("uq_people_name_tmdb_id", "people", ["name", "tmdb_id"])

    if "ix_movies_year" not in {ix["name"] for ix in inspector.get_indexes("movies")}:
        op.create_index("ix_movies_year", "movies", ["year"], unique=False)

    if "ix_roles_role_type_movie_id" not in {ix["name"] for ix in inspector.get_indexes("roles")}:
        op.create_index(
            "ix_roles_role_type_movie_id", "roles", ["role_type", "movie_id"], unique=False
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ix_roles_role_type_movie_id" in {ix["name"] for ix in inspector.get_indexes("roles")}:
        op.drop_index("ix_roles_role_type_movie_id", table_name="roles")

    if "ix_movies_year" in {ix["name"] for ix in inspector.get_indexes("movies")}:
        op.drop_index("ix_movies_year", table_name="movies")

    if bind.dialect.name == "sqlite":
        if "uq_people_name_tmdb_id" in {ix["name"] for ix in inspector.get_indexes("people")}:
            op.drop_index("uq_people_name_tmdb_id", table_name="people")
    else:
        if "uq_people_name_tmdb_id" in {
            ck["name"] for ck in inspector.get_unique_constraints("people")
        }:
            op.drop_constraint("uq_people_name_tmdb_id", "people", type_="unique")
