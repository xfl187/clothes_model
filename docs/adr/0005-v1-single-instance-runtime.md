# ADR-0005: V1 single-instance runtime

- Status: Accepted
- Date: 2026-09-24

## Context

V1 uses SQLite and an in-process scheduler. Starting multiple application replicas or Uvicorn workers without distributed task-claim coordination could duplicate external provider work, fees, and output processing.

## Decision

Deploy V1 on one fixed Linux server using Docker Compose with:

- Caddy as the HTTPS reverse proxy;
- one application container serving the Backend and the built Web Admin;
- exactly one Backend replica;
- exactly one Uvicorn worker;
- one scheduler in the same process as the HTTP application;
- persistent private volumes for SQLite, application files, and the runtime instance lock;
- secrets injected by read-only secret files or the host environment, never baked into images.

When scheduler ownership is enabled, application startup must acquire an advisory instance lock in the persistent data directory. Failure to acquire the lock causes startup to fail fast. Health/readiness must expose safe ownership status without exposing paths or secrets.

V1 does not introduce Redis, Kafka, Celery, PostgreSQL, Kubernetes, an independent worker fleet, or multiple ComfyUI scheduling nodes.

Horizontal scaling is prohibited until a later ADR replaces the persistence and task-claim coordination model. Increasing replicas or Uvicorn workers alone is not a supported deployment change.

## Consequences

- The runtime matches the Product Spec's simple fixed-server deployment.
- Duplicate scheduler ownership is prevented by both deployment configuration and a runtime guard.
- HTTP and scheduling availability share one process failure domain in V1.
- Multi-instance availability or throughput improvements require deliberate migration work rather than an operational toggle.
