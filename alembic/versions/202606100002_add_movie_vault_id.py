"""Add stable Vault IDs to movies.

Revision ID: 202606100002
Revises: 202606100001
Create Date: 2026-06-10 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606100002"
down_revision: Union[str, None] = "202606100001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("vault_id", sa.String(length=20), nullable=True))
    op.execute(
        """
        UPDATE movies
        SET vault_id = (
            SELECT provider_id
            FROM movie_ingest_provenance
            WHERE movie_ingest_provenance.movie_id = movies.id
              AND movie_ingest_provenance.provider = 'legacy_vault_csv'
        )
        WHERE vault_id IS NULL
        """
    )
    op.create_index("ix_movies_vault_id", "movies", ["vault_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_movies_vault_id", table_name="movies")
    op.drop_column("movies", "vault_id")
