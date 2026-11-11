"""Baseline: the ledger table as it existed before Phase 3.

Databases created by the old create_all() already have this table; it is only created when missing.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("verification_ledger"):
        return
    op.create_table(
        "verification_ledger",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("media_reference_id", sa.String()),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("composite_score", sa.Float()),
        sa.Column("risk_category", sa.String()),
        sa.Column("enforcement_action", sa.String()),
        sa.Column("signal_telemetry", sa.JSON()),
        sa.Column("previous_hash", sa.String(), nullable=False),
        sa.Column("current_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_verification_ledger_id", "verification_ledger", ["id"])
    op.create_index("ix_verification_ledger_media_reference_id", "verification_ledger", ["media_reference_id"])


def downgrade() -> None:
    op.drop_table("verification_ledger")
