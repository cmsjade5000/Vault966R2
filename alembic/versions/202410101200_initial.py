"""initial

Revision ID: 202410101200
Revises:
Create Date: 2024-10-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "202410101200"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

role_type_enum = sa.Enum("ACTOR", "DIRECTOR", "WRITER", name="roletype")


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("plot", sa.Text(), nullable=True),
        sa.Column("imdb_id", sa.String(length=20), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("poster_url", sa.String(length=500), nullable=True),
        sa.Column("backdrop_url", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("imdb_id"),
    )
    op.create_index(op.f("ix_movies_id"), "movies", ["id"], unique=False)
    op.create_index(op.f("ix_movies_title"), "movies", ["title"], unique=False)

    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_genres_name"), "genres", ["name"], unique=False)

    op.create_table(
        "moods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("emoji", sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_moods_name"), "moods", ["name"], unique=False)

    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("imdb_id", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_people_name"), "people", ["name"], unique=False)

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("role_type", role_type_enum, nullable=False),
        sa.Column("character_name", sa.String(length=200), nullable=True),
        sa.Column("billing_order", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_movie_id"), "roles", ["movie_id"], unique=False)
    op.create_index(op.f("ix_roles_person_id"), "roles", ["person_id"], unique=False)
    op.create_index(op.f("ix_roles_role_type"), "roles", ["role_type"], unique=False)

    op.create_table(
        "movie_genres",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["genre_id"], ["genres.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("movie_id", "genre_id"),
    )

    op.create_table(
        "movie_moods",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("mood_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mood_id"], ["moods.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("movie_id", "mood_id"),
    )


def downgrade() -> None:
    op.drop_table("movie_moods")
    op.drop_table("movie_genres")
    op.drop_index(op.f("ix_roles_role_type"), table_name="roles")
    op.drop_index(op.f("ix_roles_person_id"), table_name="roles")
    op.drop_index(op.f("ix_roles_movie_id"), table_name="roles")
    op.drop_table("roles")
    op.drop_index(op.f("ix_people_name"), table_name="people")
    op.drop_table("people")
    op.drop_index(op.f("ix_moods_name"), table_name="moods")
    op.drop_table("moods")
    op.drop_index(op.f("ix_genres_name"), table_name="genres")
    op.drop_table("genres")
    op.drop_index(op.f("ix_movies_title"), table_name="movies")
    op.drop_index(op.f("ix_movies_id"), table_name="movies")
    op.drop_table("movies")
    role_type_enum.drop(op.get_bind(), checkfirst=True)
