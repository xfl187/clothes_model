# Database migrations

Alembic is the sole production schema migration mechanism. Run migrations
serially through `python -m clothes_model.infrastructure.database.migrations`.

The Phase 1 baseline revision intentionally creates no business tables. The
Phase 2 revision adds only authentication/session metadata, throttle and audit
state, idempotency records, uploads, stored objects, assets/subtypes, and asset
references. Job, provider, workflow, output, and outfit tables remain outside
this phase.

The Phase 2 schema enforces foreign keys, lifecycle checks, uniqueness, subtype
compatibility, immutable asset kind, reference-protected deletion, and shared
stored-object reference counts. Repository adapters use the same application
Unit of Work so a service operation has one explicit transaction boundary.
