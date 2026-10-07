"""Add V1.1 layered-outfit sessions, branches, revisions, and layers.

Revision ID: 20261007_0008
Revises: 20261007_0007
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0008"
down_revision: str | None = "20261007_0007"
branch_labels: str | None = None
depends_on: str | None = None

_DEFINITIONS = (
    ("inner_top", "torso", 1, '["outerwear"]', '["dress"]'),
    ("lower_body", "lower", 2, '["outerwear"]', '["dress"]'),
    ("outerwear", "outer", 3, '["inner_top", "lower_body", "dress"]', "[]"),
    ("dress", "full", 1, '["outerwear"]', '["inner_top", "lower_body"]'),
)
_ROLE_CHECK = "role IN ('inner_top', 'outerwear', 'lower_body', 'dress')"


def upgrade() -> None:
    op.create_table(
        "layer_type_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("body_region", sa.String(48), nullable=False),
        sa.Column("layer_order", sa.Integer(), nullable=False),
        sa.Column("compatible_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("conflicting_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("required_capabilities_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(_ROLE_CHECK, name="role"),
        sa.UniqueConstraint("definition_version", "role", name="uq_layer_type_definition_role"),
    )
    for role, region, layer_order, compatible, conflicting in _DEFINITIONS:
        op.execute(
            sa.text(
                "INSERT INTO layer_type_definitions "
                "(id, definition_version, role, body_region, layer_order, "
                "compatible_roles_json, conflicting_roles_json, required_capabilities_json, "
                "created_at) VALUES "
                "(:id, 1, :role, :region, :layer_order, :compatible, :conflicting, "
                "'[\"sequential_layering\"]', CURRENT_TIMESTAMP)"
            ).bindparams(
                id=f"layer-type-v1-{role}",
                role=role,
                region=region,
                layer_order=layer_order,
                compatible=compatible,
                conflicting=conflicting,
            )
        )

    op.create_table(
        "outfit_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_scope_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "person_asset_id",
            sa.String(36),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("layer_definition_version", sa.Integer(), nullable=False),
        sa.Column("main_branch_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_outfit_sessions_owner",
        "outfit_sessions",
        ["owner_scope_id", "created_at"],
    )

    op.create_table(
        "outfit_branches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("outfit_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("route", sa.String(16), nullable=False),
        sa.Column("favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_mainline", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("head_revision_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("route IN ('split', 'dress')", name="route"),
    )
    op.create_index("ix_outfit_branches_session", "outfit_branches", ["session_id"])

    op.create_table(
        "outfit_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("outfit_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("outfit_branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_revision_id", sa.String(36), nullable=True),
        sa.Column("parent_revision_id", sa.String(36), nullable=True),
        sa.Column("layers_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_outfit_revisions_branch",
        "outfit_revisions",
        ["branch_id", "created_at"],
    )

    op.create_table(
        "outfit_layers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("outfit_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("outfit_branches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column(
            "garment_asset_id",
            sa.String(36),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("layer_order", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="applied"),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("source_layer_id", sa.String(36), nullable=True),
        sa.Column(
            "apply_job_id",
            sa.String(36),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "selected_output_id",
            sa.String(36),
            sa.ForeignKey("generated_outputs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(_ROLE_CHECK, name="role"),
        sa.CheckConstraint("state IN ('applied', 'pending_reapply')", name="state"),
    )
    op.create_index("ix_outfit_layers_branch", "outfit_layers", ["branch_id"])


def downgrade() -> None:
    op.drop_index("ix_outfit_layers_branch", table_name="outfit_layers")
    op.drop_table("outfit_layers")
    op.drop_index("ix_outfit_revisions_branch", table_name="outfit_revisions")
    op.drop_table("outfit_revisions")
    op.drop_index("ix_outfit_branches_session", table_name="outfit_branches")
    op.drop_table("outfit_branches")
    op.drop_index("ix_outfit_sessions_owner", table_name="outfit_sessions")
    op.drop_table("outfit_sessions")
    op.drop_table("layer_type_definitions")
