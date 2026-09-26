# ADR-0003: SQLite, SQLAlchemy, and Alembic

- Status: Accepted
- Date: 2026-09-24

## Context

V1 is a single-user, single-instance product. It needs durable tasks, configuration, references, and migration history, but it does not need PostgreSQL or distributed coordination. Business code must not become inseparable from SQLite because a future concurrency-driven migration remains possible.

## Decision

Use SQLite as the V1 database with:

- SQLAlchemy 2 async APIs and the `sqlite+aiosqlite` dialect;
- repository and Unit of Work boundaries;
- Alembic as the sole schema-migration mechanism;
- foreign-key enforcement, WAL mode, a bounded busy timeout, short transactions, and serial migration execution;
- database files on a persistent private volume.

Application services depend on repository/UoW interfaces rather than SQLite-specific queries. SQLite-specific configuration stays in the infrastructure layer.

Phase 1 establishes connectivity, transaction, migration, and smoke-test infrastructure only. It does not create the authentication, asset, task, provider, workflow, or cleanup business schemas assigned to later roadmap phases.

## Consequences

- V1 has a low-maintenance, backup-friendly persistence baseline.
- Async interfaces integrate consistently with FastAPI, but do not change SQLite's fundamental write-concurrency limits.
- The V1 single-instance restriction is mandatory and is reinforced by ADR-0005.
- A future PostgreSQL migration will require new infrastructure adapters and migration planning, but domain/application code should remain largely independent.
