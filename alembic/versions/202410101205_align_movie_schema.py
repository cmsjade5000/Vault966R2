"""align movie schema with enrichment and provenance fields

Revision ID: 202410101205
Revises: 202410101204
Create Date: 2024-10-10 12:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "202410101205"
down_revision: Union[str, None] = "202410101204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {ix["name"] for ix in inspector.get_indexes(table)}


def _unique_constraint_covers(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints(table):
        if set(constraint.get("column_names") or []) == {column}:
            return True
    return False


def _check_constraint_exists(table: str, name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in {ck["name"] for ck in inspector.get_check_constraints(table)}


def _table_exists(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    for column in [
        sa.Column("tagline", sa.String(length=500), nullable=True),
        sa.Column("awards", sa.Text(), nullable=True),
        sa.Column("revenue", sa.BigInteger(), nullable=True),
        sa.Column("budget", sa.BigInteger(), nullable=True),
        sa.Column("metascore", sa.Integer(), nullable=True),
        sa.Column("tomato_meter", sa.Integer(), nullable=True),
        sa.Column("tomato_audience", sa.Integer(), nullable=True),
        sa.Column("last_tmdb_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_omdb_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tmdb_etag", sa.String(length=128), nullable=True),
        sa.Column("tmdb_payload_sha", sa.String(length=128), nullable=True),
        sa.Column("omdb_payload_sha", sa.String(length=128), nullable=True),
    ]:
        if not _column_exists("movies", column.name):
            op.add_column("movies", column)

    if not _index_exists("movies", "ix_movies_imdb_id") and not _unique_constraint_covers(
        "movies", "imdb_id"
    ):
        op.create_index("ix_movies_imdb_id", "movies", ["imdb_id"], unique=True)

    if not _index_exists("movies", "ix_movies_tmdb_id"):
        op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)

    if not is_sqlite and not _check_constraint_exists("movies", "ck_movies_imdb_rating_range"):
        op.create_check_constraint(
            "ck_movies_imdb_rating_range",
            "movies",
            sa.text("imdb_rating BETWEEN 0 AND 10"),
        )

    if not is_sqlite and not _check_constraint_exists("movies", "ck_movies_metascore_range"):
        op.create_check_constraint(
            "ck_movies_metascore_range",
            "movies",
            sa.text("metascore BETWEEN 0 AND 100"),
        )

    if not _table_exists("movie_cast"):
        op.create_table(
            "movie_cast",
            sa.Column(
                "movie_id",
                sa.Integer(),
                sa.ForeignKey("movies.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "person_id",
                sa.Integer(),
                sa.ForeignKey("people.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("character", sa.String(length=300), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=True),
        )
        op.create_index("ix_movie_cast_movie_id", "movie_cast", ["movie_id"], unique=False)

    if not _table_exists("movie_crew"):
        op.create_table(
            "movie_crew",
            sa.Column(
                "movie_id",
                sa.Integer(),
                sa.ForeignKey("movies.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "person_id",
                sa.Integer(),
                sa.ForeignKey("people.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("department", sa.String(length=200), nullable=True),
            sa.Column("job", sa.String(length=200), nullable=True),
        )
        op.create_index("ix_movie_crew_movie_id", "movie_crew", ["movie_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    if _index_exists("movies", "ix_movies_tmdb_id"):
        op.drop_index("ix_movies_tmdb_id", table_name="movies")

    if _index_exists("movies", "ix_movies_imdb_id"):
        op.drop_index("ix_movies_imdb_id", table_name="movies")

    if not is_sqlite and _check_constraint_exists("movies", "ck_movies_metascore_range"):
        op.drop_constraint("ck_movies_metascore_range", "movies", type_="check")

    if not is_sqlite and _check_constraint_exists("movies", "ck_movies_imdb_rating_range"):
        op.drop_constraint("ck_movies_imdb_rating_range", "movies", type_="check")

    for name in [
        "omdb_payload_sha",
        "tmdb_payload_sha",
        "tmdb_etag",
        "last_omdb_fetch_at",
        "last_tmdb_fetch_at",
        "tomato_audience",
        "tomato_meter",
        "metascore",
        "budget",
        "revenue",
        "awards",
        "tagline",
    ]:
        if _column_exists("movies", name):
            op.drop_column("movies", name)

    if _table_exists("movie_crew"):
        op.drop_index("ix_movie_crew_movie_id", table_name="movie_crew")
        op.drop_table("movie_crew")

    if _table_exists("movie_cast"):
        op.drop_index("ix_movie_cast_movie_id", table_name="movie_cast")
        op.drop_table("movie_cast")
