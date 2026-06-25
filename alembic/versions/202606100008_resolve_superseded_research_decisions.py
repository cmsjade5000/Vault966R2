"""Resolve superseded source research decisions.

Revision ID: 202606100008
Revises: 202606100007
Create Date: 2026-06-10 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202606100008"
down_revision: Union[str, None] = "202606100007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_field_decisions
        SET resolved_at = (
            SELECT later.decided_at
            FROM source_field_decisions AS later
            WHERE later.source_row_id = source_field_decisions.source_row_id
              AND later.field_name = source_field_decisions.field_name
              AND later.undone_at IS NULL
              AND (
                later.decided_at > source_field_decisions.decided_at
                OR (
                    later.decided_at = source_field_decisions.decided_at
                    AND later.id > source_field_decisions.id
                )
              )
            ORDER BY later.decided_at ASC, later.id ASC
            LIMIT 1
        )
        WHERE source_field_decisions.decision = 'needs_research'
          AND source_field_decisions.resolved_at IS NULL
          AND source_field_decisions.undone_at IS NULL
          AND EXISTS (
            SELECT 1
            FROM source_field_decisions AS later
            WHERE later.source_row_id = source_field_decisions.source_row_id
              AND later.field_name = source_field_decisions.field_name
              AND later.undone_at IS NULL
              AND (
                later.decided_at > source_field_decisions.decided_at
                OR (
                    later.decided_at = source_field_decisions.decided_at
                    AND later.id > source_field_decisions.id
                )
              )
          )
        """
    )


def downgrade() -> None:
    pass
