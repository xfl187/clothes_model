# ADR-0002: Backend modular monolith

- Status: Accepted
- Date: 2026-09-24

## Context

The Product Spec requires one fixed-server business entrypoint that owns authentication, assets, durable jobs, providers, workflows, administration, cleanup, and private data. V1 is a personal project and does not require the operational cost of microservices or an independent worker fleet.

## Decision

Build one Python 3.14 / FastAPI deployment unit using Pydantic 2, Uvicorn, and a feature-first modular-monolith layout.

The feature modules are:

- `auth`
- `assets`
- `jobs`
- `providers`
- `workflows`
- `admin`
- `cleanup`

Each feature may contain HTTP, application, domain, and infrastructure adapters as needed. Domain and application code must not depend directly on FastAPI, SQLAlchemy, SQLite, or concrete provider protocols. Cross-cutting configuration, errors, logging, database, scheduler, and storage ports live under explicit core/infrastructure boundaries.

`Outfits` is not implemented or exposed during Phase 1; it belongs to Roadmap Phase 9. V1 types must remain extensible without pre-creating V1.1 business behavior.

The Backend dependency and quality baseline uses `uv`, Ruff, Pyright, and Pytest.

## Consequences

- Deployment and local operation remain simple.
- Module boundaries and ports preserve a path to a future worker extraction without paying that cost now.
- A module may not bypass another module's application boundary by directly reaching into its persistence implementation.
- Scaling the application horizontally requires an explicit later architecture decision rather than a configuration-only replica increase.
