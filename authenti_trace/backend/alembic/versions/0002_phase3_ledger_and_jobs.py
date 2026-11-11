"""Phase 3: ledger seq, hash_version, versions, unique head guards, and the jobs table.

Old rows get seq 1..N in created_at order and hash_version 1 (their hashes stay valid under the old rule).
Fails with a unique-index error if an old database already contains a forked chain (two rows with the same
previous_hash). Inspect that database by hand before upgrading.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("verification_ledger")}

    with op.batch_alter_table("verification_ledger") as batch:
        if "seq" not in columns:
            batch.add_column(sa.Column("seq", sa.Integer(), nullable=True))
        if "hash_version" not in columns:
            batch.add_column(sa.Column("hash_version", sa.Integer(), nullable=True))
        if "versions" not in columns:
            batch.add_column(sa.Column("versions", sa.JSON(), nullable=True))

    ids = bind.execute(
        sa.text("SELECT id FROM verification_ledger WHERE seq IS NULL ORDER BY created_at, id")
    ).scalars().all()
    start = bind.execute(sa.text("SELECT COALESCE(MAX(seq), 0) FROM verification_ledger")).scalar()
    for offset, row_id in enumerate(ids, start=1):
        bind.execute(
            sa.text("UPDATE verification_ledger SET seq = :seq, hash_version = 1 WHERE id = :id"),
            {"seq": start + offset, "id": row_id},
        )
    bind.execute(sa.text("UPDATE verification_ledger SET hash_version = 1 WHERE hash_version IS NULL"))

    with op.batch_alter_table("verification_ledger") as batch:
        batch.alter_column("seq", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("hash_version", existing_type=sa.Integer(), nullable=False)

    existing_indexes = {i["name"] for i in sa.inspect(bind).get_indexes("verification_ledger")}
    if "uq_ledger_seq" not in existing_indexes:
        op.create_index("uq_ledger_seq", "verification_ledger", ["seq"], unique=True)
    if "uq_ledger_previous_hash" not in existing_indexes:
        op.create_index("uq_ledger_previous_hash", "verification_ledger", ["previous_hash"], unique=True)

    if not sa.inspect(bind).has_table("verification_jobs"):
        op.create_table(
            "verification_jobs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("media_id", sa.String(), nullable=False),
            sa.Column("file_path", sa.String(), nullable=False),
            sa.Column("file_hash", sa.String(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("report_id", sa.String()),
            sa.Column("error", sa.String()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_index("ix_verification_jobs_status", "verification_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("verification_jobs")
    op.drop_index("uq_ledger_previous_hash", table_name="verification_ledger")
    op.drop_index("uq_ledger_seq", table_name="verification_ledger")
    with op.batch_alter_table("verification_ledger") as batch:
        batch.drop_column("versions")
        batch.drop_column("hash_version")
        batch.drop_column("seq")
