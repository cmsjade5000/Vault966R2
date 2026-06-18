"""Add immutable collection source snapshots and reconciliation records.

Revision ID: 202606100004
Revises: 202606100003
Create Date: 2026-06-10 03:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606100004"
down_revision: Union[str, None] = "202606100003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_csv", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("uploaded_by_profile_id", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_sha256"),
    )
    op.create_index(
        "ix_source_snapshots_status_uploaded",
        "source_snapshots",
        ["status", "uploaded_at"],
        unique=False,
    )
    op.create_table(
        "source_movie_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("normalized_title", sa.String(length=300), nullable=False),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("director", sa.String(length=500), nullable=True),
        sa.Column("normalized_directors", sa.JSON(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("genre", sa.String(length=200), nullable=True),
        sa.Column("content_rating", sa.Text(), nullable=True),
        sa.Column("release_date", sa.String(length=80), nullable=True),
        sa.Column("hd", sa.Boolean(), nullable=True),
        sa.Column("duplicate_group", sa.String(length=64), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "row_number", name="uq_source_movie_rows_snapshot_row"),
    )
    op.create_index(
        "ix_source_movie_rows_snapshot_id",
        "source_movie_rows",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_movie_rows_normalized_title",
        "source_movie_rows",
        ["normalized_title"],
        unique=False,
    )
    op.create_table(
        "source_reconciliation_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=True),
        sa.Column("match_type", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("candidate_movie_ids", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_row_id"], ["source_movie_rows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row_id", name="uq_source_reconciliation_matches_row"),
    )
    op.create_index(
        "ix_source_reconciliation_matches_movie_id",
        "source_reconciliation_matches",
        ["movie_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_reconciliation_matches_type",
        "source_reconciliation_matches",
        ["match_type"],
        unique=False,
    )
    op.create_table(
        "source_field_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=30), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("selected_value", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("decided_by_profile_id", sa.Integer(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["decided_by_profile_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_row_id"], ["source_movie_rows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row_id", "field_name", name="uq_source_field_decisions_field"),
    )
    op.create_index(
        "ix_source_field_decisions_movie_id",
        "source_field_decisions",
        ["movie_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_field_decisions_decision",
        "source_field_decisions",
        ["decision"],
        unique=False,
    )
    op.create_table(
        "owned_movie_copies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=False),
        sa.Column("hd", sa.Boolean(), nullable=True),
        sa.Column("source_title", sa.String(length=300), nullable=False),
        sa.Column("source_year", sa.Integer(), nullable=True),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_row_id"], ["source_movie_rows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_row_id", name="uq_owned_movie_copies_source_row"),
    )
    op.create_index(
        "ix_owned_movie_copies_movie_id",
        "owned_movie_copies",
        ["movie_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_owned_movie_copies_movie_id", table_name="owned_movie_copies")
    op.drop_table("owned_movie_copies")
    op.drop_index("ix_source_field_decisions_decision", table_name="source_field_decisions")
    op.drop_index("ix_source_field_decisions_movie_id", table_name="source_field_decisions")
    op.drop_table("source_field_decisions")
    op.drop_index(
        "ix_source_reconciliation_matches_type",
        table_name="source_reconciliation_matches",
    )
    op.drop_index(
        "ix_source_reconciliation_matches_movie_id",
        table_name="source_reconciliation_matches",
    )
    op.drop_table("source_reconciliation_matches")
    op.drop_index("ix_source_movie_rows_normalized_title", table_name="source_movie_rows")
    op.drop_index("ix_source_movie_rows_snapshot_id", table_name="source_movie_rows")
    op.drop_table("source_movie_rows")
    op.drop_index("ix_source_snapshots_status_uploaded", table_name="source_snapshots")
    op.drop_table("source_snapshots")
