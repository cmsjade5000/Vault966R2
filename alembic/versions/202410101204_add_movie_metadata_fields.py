"""add movie metadata fields

Revision ID: 202410101204
Revises: 202410101203
Create Date: 2024-10-10 12:04:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "202410101204"
down_revision: Union[str, None] = "202410101203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    # Add movie metadata columns only if they don't already exist (idempotent)
    _add_column_if_missing("movies", sa.Column("imdb_rating", sa.Float(), nullable=True))
    _add_column_if_missing("movies", sa.Column("imdb_votes", sa.Integer(), nullable=True))
    _add_column_if_missing("movies", sa.Column("metascore", sa.Integer(), nullable=True))
    _add_column_if_missing("movies", sa.Column("tomato_meter", sa.Integer(), nullable=True))
    _add_column_if_missing("movies", sa.Column("tomato_audience", sa.Integer(), nullable=True))
    _add_column_if_missing("movies", sa.Column("plot", sa.Text(), nullable=True))
    _add_column_if_missing("movies", sa.Column("awards", sa.Text(), nullable=True))


def downgrade() -> None:
    # Drop columns only if present (idempotent)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("movies")}
    for name in [
        "awards",
        "plot",
        "tomato_audience",
        "tomato_meter",
        "metascore",
        "imdb_votes",
        "imdb_rating",
    ]:
        if name in existing:
            op.drop_column("movies", name)
