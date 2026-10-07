"""Add storage retention policy and scan records.

Revision ID: 20261007_0007
Revises: 20260929_0006
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0007"
down_revision: str | None = "20260929_0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "retention_policy",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column(
            "unfavorited_output_days", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column("intermediate_file_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 'default'", name="singleton"),
        sa.CheckConstraint("unfavorited_output_days >= 1", name="unfavorited_output_days"),
        sa.CheckConstraint("intermediate_file_days >= 1", name="intermediate_file_days"),
    )
    op.execute(
        sa.text(
            "INSERT INTO retention_policy "
            "(id, unfavorited_output_days, intermediate_file_days, updated_at) "
            "VALUES ('default', 30, 7, CURRENT_TIMESTAMP)"
        )
    )
    op.create_table(
        "storage_scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reclaimable_files", sa.Integer(), nullable=False),
        sa.Column("reclaimable_bytes", sa.Integer(), nullable=False),
        sa.Column("protected_files", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("storage_scans")
    op.drop_table("retention_policy")
