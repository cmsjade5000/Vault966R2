"""convert providers/languages/countries to jsonb

Revision ID: 9ab64fd9beb0
Revises: 75cf58420676
Create Date: 2025-09-28 19:24:00
"""

from typing import Optional

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9ab64fd9beb0"
down_revision: Optional[str] = "75cf58420676"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Convert TEXT -> JSONB (idempotent casts; NULL stays NULL)
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN where_to_watch TYPE jsonb
        USING CASE WHEN where_to_watch IS NULL THEN NULL ELSE where_to_watch::jsonb END;
        """
    )
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN languages TYPE jsonb
        USING CASE WHEN languages IS NULL THEN NULL ELSE languages::jsonb END;
        """
    )
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN countries TYPE jsonb
        USING CASE WHEN countries IS NULL THEN NULL ELSE countries::jsonb END;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Convert JSONB -> TEXT (stringify)
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN where_to_watch TYPE text
        USING CASE WHEN where_to_watch IS NULL THEN NULL ELSE where_to_watch::text END;
        """
    )
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN languages TYPE text
        USING CASE WHEN languages IS NULL THEN NULL ELSE languages::text END;
        """
    )
    op.execute(
        """
        ALTER TABLE movies
        ALTER COLUMN countries TYPE text
        USING CASE WHEN countries IS NULL THEN NULL ELSE countries::text END;
        """
    )
