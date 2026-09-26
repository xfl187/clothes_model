# ADR-0004: OpenAPI contract ownership

- Status: Accepted
- Date: 2026-09-24

## Context

Backend, Android, and Web Admin must share task states, errors, pagination, idempotency, immutable version references, and provider capabilities. If each platform defines these independently, clients can silently diverge from server behavior before the first end-to-end implementation exists.

## Decision

Use spec-first OpenAPI 3.0.3 as the single cross-platform HTTP contract source.

- Canonical, domain-organized sources live under `contracts/openapi/`.
- CI resolves them into one bundled artifact.
- Backend Pydantic contract models, the Android client, and Web types/client are generated from the same contract.
- A contract mock server runs directly from the bundled artifact.
- Backend request/response contract tests prove implementation conformance.
- Generated artifacts are committed, marked as generated, never manually edited, and checked for regeneration drift.

The Product Spec remains authoritative for product behavior. OpenAPI expresses that confirmed behavior at the transport boundary and must not invent new product semantics.

Breaking changes require either a compatible migration within `/api/v1` or a new API version. Additive changes must preserve older clients' safe unknown-state/error fallback behavior.

## Consequences

- Android and Web can integrate against a mock before production Backend behavior exists.
- Contract changes are explicit and reviewable across all consumers.
- Generation tooling becomes part of the build baseline and must be pinned.
- Backend implementation has some generated/manual adapter boundaries, but it may not replace the canonical contract with an independently authored schema.
