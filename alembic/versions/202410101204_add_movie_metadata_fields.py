"""add movie metadata fields

Revision ID: 202410101204
Revises: 202410101203
Create Date: 2024-10-10 13:05:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202410101204"
down_revision: Union[str, None] = "202410101203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("imdb_rating", sa.Float(), nullable=True))
    op.add_column("movies", sa.Column("imdb_votes", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("rt_score", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("where_to_watch", sa.Text(), nullable=True))
    op.add_column("movies", sa.Column("languages", sa.Text(), nullable=True))
    op.add_column("movies", sa.Column("countries", sa.Text(), nullable=True))
    op.add_column("movies", sa.Column("collection", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("movies", "collection")
    op.drop_column("movies", "countries")
    op.drop_column("movies", "languages")
    op.drop_column("movies", "where_to_watch")
    op.drop_column("movies", "rt_score")
    op.drop_column("movies", "imdb_votes")
    op.drop_column("movies", "imdb_rating")
