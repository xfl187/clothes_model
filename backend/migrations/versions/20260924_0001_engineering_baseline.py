"""Establish the migration mechanism without business schema.

Revision ID: 20260924_0001
Revises: None
Create Date: 2026-09-24
"""

revision: str = "20260924_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Intentionally empty: later phases own all business tables."""


def downgrade() -> None:
    """Intentionally empty: Alembic removes its version marker."""
