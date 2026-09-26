# Backend module boundaries

The Backend is one deployable FastAPI modular monolith.

```text
HTTP / infrastructure adapters -> application -> domain
                    core ports -> domain-safe shared types
```

- `clothes_model.api` owns FastAPI assembly, middleware, health, and route registration.
- `clothes_model.core` owns configuration, logging, and transport-neutral problem data.
- `clothes_model.modules.<feature>.http` is an inbound adapter only.
- Application and domain packages must not import FastAPI, SQLAlchemy,
  SQLite, or concrete provider protocols.
- `clothes_model.generated` comes from canonical bundled OpenAPI and is never hand-edited.
- `core.persistence` owns repository and Unit of Work ports; SQLAlchemy and
  SQLite remain inside `infrastructure.database`.
- `infrastructure.scheduler` owns the in-process lifecycle and advisory
  single-instance lock. Its Phase 1 job source and scheduler execute no work.

Phase 2 adds persistence ports and SQLAlchemy adapters for authentication,
uploads, private stored-object metadata, assets, references, idempotency, and
security audit metadata. HTTP behavior, cryptography, filesystem storage, and
future job/provider/workflow schemas remain owned by their planned tasks.
