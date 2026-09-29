"""Add stable ownership and local-first asset lifecycle fields.

Revision ID: 20260929_0006
Revises: 20260928_0005
Create Date: 2026-09-29
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0006"
down_revision: str | None = "20260928_0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    owner_id, server_id = str(uuid4()), str(uuid4())
    op.create_table(
        "owner_scopes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "server_identity",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.execute(
        sa.text("INSERT INTO owner_scopes (id, created_at) VALUES (:id, CURRENT_TIMESTAMP)")
        .bindparams(id=owner_id)
    )
    op.execute(
        sa.text("INSERT INTO server_identity (id, created_at) VALUES (:id, CURRENT_TIMESTAMP)")
        .bindparams(id=server_id)
    )

    op.add_column("access_tokens", sa.Column("owner_scope_id", sa.String(36), nullable=True))
    op.execute(
        sa.text("UPDATE access_tokens SET owner_scope_id=:owner WHERE scope='app'")
        .bindparams(owner=owner_id)
    )

    op.add_column("assets", sa.Column("owner_scope_id", sa.String(36), nullable=True))
    op.add_column(
        "assets",
        sa.Column(
            "durable_client_copy_confirmed", sa.Boolean(), nullable=False, server_default="0"
        ),
    )
    op.add_column("assets", sa.Column("client_asset_id", sa.String(36), nullable=True))
    op.add_column("assets", sa.Column("cleanup_after", sa.DateTime(), nullable=True))
    op.execute(sa.text("UPDATE assets SET owner_scope_id=:owner").bindparams(owner=owner_id))
    op.create_index(
        "ix_assets_owner_list", "assets", ["owner_scope_id", "created_at", "id"], unique=False
    )

    op.add_column("upload_sessions", sa.Column("owner_scope_id", sa.String(36), nullable=True))
    op.add_column("upload_sessions", sa.Column("target_asset_id", sa.String(36), nullable=True))
    op.execute(
        sa.text(
            "UPDATE upload_sessions SET owner_scope_id=("
            "SELECT owner_scope_id FROM access_tokens "
            "WHERE access_tokens.id=upload_sessions.actor_token_id"
            ")"
        )
    )
    op.execute(
        sa.text("UPDATE upload_sessions SET owner_scope_id=:owner WHERE owner_scope_id IS NULL")
        .bindparams(owner=owner_id)
    )
    op.add_column("jobs", sa.Column("owner_scope_id", sa.String(36), nullable=True))
    op.execute(
        sa.text(
            "UPDATE jobs SET owner_scope_id=(SELECT owner_scope_id FROM assets "
            "WHERE assets.id=jobs.garment_asset_id)"
        )
    )
    op.execute(
        sa.text("UPDATE jobs SET owner_scope_id=:owner WHERE owner_scope_id IS NULL").bindparams(
            owner=owner_id
        )
    )
    op.create_index("ix_jobs_owner_list", "jobs", ["owner_scope_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner_list", table_name="jobs")
    op.drop_column("jobs", "owner_scope_id")
    op.drop_column("upload_sessions", "target_asset_id")
    op.drop_column("upload_sessions", "owner_scope_id")
    op.drop_index("ix_assets_owner_list", table_name="assets")
    op.drop_column("assets", "cleanup_after")
    op.drop_column("assets", "client_asset_id")
    op.drop_column("assets", "durable_client_copy_confirmed")
    op.drop_column("assets", "owner_scope_id")
    op.drop_column("access_tokens", "owner_scope_id")
    op.drop_table("server_identity")
    op.drop_table("owner_scopes")
