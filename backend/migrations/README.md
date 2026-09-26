# Database migrations

Alembic is the sole production schema migration mechanism. Run migrations
serially through `python -m clothes_model.infrastructure.database.migrations`.

The Phase 1 baseline revision intentionally creates no business tables. The
only table after upgrade is Alembic's own version table.
