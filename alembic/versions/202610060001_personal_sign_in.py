"""Add personal sign-in and reversible profile archives; archive no rows."""

from alembic import op
import sqlalchemy as sa

revision = "202610060001"
down_revision = "202607060001"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("personal_sign_in_only", "local_setup_only"):
        op.add_column(
            "app_setup",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    op.add_column("profiles", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("profiles", sa.Column("archived_name", sa.String(80), nullable=True))
    op.add_column("profiles", sa.Column("archived_batch_id", sa.String(36), nullable=True))
    op.add_column(
        "app_setup",
        sa.Column("unlock_revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "profiles",
        sa.Column("session_revision", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "profile_archive_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("previous_setup_completed", sa.Boolean(), nullable=False),
        sa.Column("previous_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("previous_owner_profile_id", sa.Integer(), nullable=True),
        sa.Column("previous_personal_sign_in_only", sa.Boolean(), nullable=False),
        sa.Column("previous_local_setup_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "setup_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("generation", sa.String(36), nullable=False),
        sa.Column("owner_name", sa.String(80), nullable=False),
        sa.Column("code_salt", sa.String(64), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("issued_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("browser_hash", sa.String(64), nullable=True),
        sa.Column("bound_at", sa.Integer(), nullable=True),
        sa.Column("consumed_at", sa.Integer(), nullable=True),
    )


def downgrade():
    # Old code ignores archive state; fail closed once any archive was created.
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM profile_archive_batches")).scalar():
        raise RuntimeError(
            "Restore accounts with archive-aware code; downgrade after archival is unsafe"
        )
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM setup_grants")).scalar():
        raise RuntimeError("Setup grant issued; downgrade to unprotected setup is unsafe")
    op.drop_table("setup_grants")
    op.drop_table("profile_archive_batches")
    for name in ("session_revision", "archived_batch_id", "archived_name", "archived_at"):
        op.drop_column("profiles", name)
    for name in ("unlock_revision", "local_setup_only", "personal_sign_in_only"):
        op.drop_column("app_setup", name)
