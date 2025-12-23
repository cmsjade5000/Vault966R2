"""create movie_ingest_provenance table

Revision ID: 202410101206
Revises: 202410101205
Create Date: 2024-10-10 12:06:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202410101206"
down_revision: Union[str, None] = "202410101205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _index_exists(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {index["name"] for index in inspector.get_indexes(table)}


def _unique_constraint_exists(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {constraint["name"] for constraint in inspector.get_unique_constraints(table)}


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if not _table_exists("movie_ingest_provenance"):
        op.create_table(
            "movie_ingest_provenance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "movie_id",
                sa.Integer(),
                sa.ForeignKey("movies.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("provider_id", sa.String(length=100), nullable=True),
            sa.Column(
                "ingested_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("payload_sha", sa.String(length=128), nullable=True),
            sa.Column("etag", sa.String(length=128), nullable=True),
            sa.Column("source_url", sa.String(length=500), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    if not _index_exists("movie_ingest_provenance", "ix_movie_ingest_provenance_movie_id"):
        op.create_index(
            "ix_movie_ingest_provenance_movie_id",
            "movie_ingest_provenance",
            ["movie_id"],
        )

    if is_sqlite:
        if not _index_exists(
            "movie_ingest_provenance", "uq_movie_ingest_provenance_movie_provider"
        ):
            op.create_index(
                "uq_movie_ingest_provenance_movie_provider",
                "movie_ingest_provenance",
                ["movie_id", "provider"],
                unique=True,
            )
    else:
        if not _unique_constraint_exists(
            "movie_ingest_provenance", "uq_movie_ingest_provenance_movie_provider"
        ):
            op.create_unique_constraint(
                "uq_movie_ingest_provenance_movie_provider",
                "movie_ingest_provenance",
                ["movie_id", "provider"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if _unique_constraint_exists(
        "movie_ingest_provenance", "uq_movie_ingest_provenance_movie_provider"
    ):
        if not is_sqlite:
            op.drop_constraint(
                "uq_movie_ingest_provenance_movie_provider",
                "movie_ingest_provenance",
                type_="unique",
            )
    if is_sqlite and _index_exists(
        "movie_ingest_provenance", "uq_movie_ingest_provenance_movie_provider"
    ):
        op.drop_index(
            "uq_movie_ingest_provenance_movie_provider",
            table_name="movie_ingest_provenance",
        )

    if _index_exists("movie_ingest_provenance", "ix_movie_ingest_provenance_movie_id"):
        op.drop_index(
            "ix_movie_ingest_provenance_movie_id",
            table_name="movie_ingest_provenance",
        )

    if _table_exists("movie_ingest_provenance"):
        op.drop_table("movie_ingest_provenance")
