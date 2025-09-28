"""add movie enrichment columns

Revision ID: 75cf58420676
Revises: c453b689bb5c
Create Date: 2025-09-28 19:06:12.740081

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "75cf58420676"
down_revision: Union[str, None] = "c453b689bb5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_col_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    # Text/URLs (TMDb core & pretty stuff)
    _add_col_if_missing("movies", sa.Column("tagline", sa.Text(), nullable=True))
    _add_col_if_missing("movies", sa.Column("poster_url", sa.Text(), nullable=True))
    _add_col_if_missing("movies", sa.Column("backdrop_url", sa.Text(), nullable=True))
    _add_col_if_missing("movies", sa.Column("collection", sa.Text(), nullable=True))

    # Numbers (box office + alt rating)
    _add_col_if_missing("movies", sa.Column("rt_score", sa.Integer(), nullable=True))
    _add_col_if_missing("movies", sa.Column("revenue", sa.BigInteger(), nullable=True))
    _add_col_if_missing("movies", sa.Column("budget", sa.BigInteger(), nullable=True))

    # Provenance / caching
    _add_col_if_missing(
        "movies", sa.Column("last_tmdb_fetch_at", sa.DateTime(timezone=True), nullable=True)
    )
    _add_col_if_missing(
        "movies", sa.Column("last_omdb_fetch_at", sa.DateTime(timezone=True), nullable=True)
    )
    _add_col_if_missing("movies", sa.Column("tmdb_etag", sa.Text(), nullable=True))
    _add_col_if_missing("movies", sa.Column("tmdb_payload_sha", sa.Text(), nullable=True))
    _add_col_if_missing("movies", sa.Column("omdb_payload_sha", sa.Text(), nullable=True))

    # JSON blobs (providers / languages / countries)
    _add_col_if_missing("movies", sa.Column("where_to_watch", sa.JSON(), nullable=True))
    _add_col_if_missing("movies", sa.Column("languages", sa.JSON(), nullable=True))
    _add_col_if_missing("movies", sa.Column("countries", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("movies")}
    for name in [
        "countries",
        "languages",
        "where_to_watch",
        "omdb_payload_sha",
        "tmdb_payload_sha",
        "tmdb_etag",
        "last_omdb_fetch_at",
        "last_tmdb_fetch_at",
        "budget",
        "revenue",
        "rt_score",
        "collection",
        "backdrop_url",
        "poster_url",
        "tagline",
    ]:
        if name in existing:
            op.drop_column("movies", name)
