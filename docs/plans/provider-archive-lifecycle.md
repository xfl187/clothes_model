# Provider Archive Lifecycle Implementation Plan

Status: ready for implementation
Updated: 2026-09-30

## Progress

- Task 1 — COMPLETE
- Task 2 — COMPLETE
- Task 3 — COMPLETE
- Task 4 — NOT_STARTED

Last verified: 2026-09-30 — contract verification, generated artifact drift, Backend/Web generated-client type checks, Android generated-client compilation, focused Provider/job HTTP tests, Ruff, Pyright, Web unit tests, Web lint, and the production Web build passed.

## Goal

Allow an administrator to archive and later restore an LLM Provider that must remain for job history. Archived Providers retain credentials, revisions, and historical references, but cannot be selected for new work or made default.

Confirmed behavior is recorded in:

- `docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md`
- `docs/product-flow.md`

## Current State and Delta

The persisted Provider state already permits `disabled`, so no database migration is required. The Backend currently exposes create, update, validate, enable, default, and permanent-delete operations; the Web Admin exposes the same subset. Permanent deletion correctly rejects historical references but offers no lifecycle alternative.

The implementation must add archive/restore contract operations, enforce the archived state at all new-work boundaries, preserve locked historical execution, and expose the lifecycle in Web Admin.

## Tasks

### Task 1 — Extend and regenerate the Provider API contract

Affected:

- `contracts/openapi/openapi.yaml`
- `contracts/openapi/paths/providers.yaml`
- generated Web and Android API clients

Work:

- add CSRF-protected archive and restore operations;
- return the redacted Provider configuration after each transition;
- document default/system-managed/state conflicts;
- regenerate and verify contract artifacts.

Verify:

- contract lint, bundle, generated-client type checks, and existing boundary checks pass.

### Task 2 — Implement Backend lifecycle rules

Affected:

- Provider application service and HTTP router;
- focused Provider HTTP tests.

Work:

- archive a non-system, non-default Provider by setting `state=disabled`;
- make repeated archive safe and restore `disabled` to `inactive`;
- reject update, validation, enable, and default selection while archived;
- exclude archived Providers from App-facing available Provider results and new job creation;
- keep revision-based invocation available for already-created jobs;
- retain existing permanent-delete restrictions.

Verify:

- tests cover referenced Provider archive, default rejection, App-list exclusion, new-job rejection, historical invocation continuity, restore, and delete behavior;
- Ruff and Pyright pass.

### Task 3 — Add Web Admin archive and restore flow

Affected:

- Provider gateway;
- Provider Admin page and styles;
- component tests.

Work:

- show archived status without dropping the item from administrative history;
- replace the misleading delete-only path with archive confirmation for referenced/retained configurations;
- disable editing, validation, enable, and default actions while archived;
- provide restore, returning the Provider to inactive state;
- keep permanent delete available only as a distinct destructive action and preserve server-side conflict messages.

Verify:

- component tests cover archive confirmation, archived read-only state, restore, and permanent delete;
- Web lint, typecheck, tests, and production build pass.

### Task 4 — Integrated verification and deployment smoke

Work:

- rebuild the development Backend/Web image;
- archive a non-default historical Provider through the real API or UI;
- confirm it remains visible in Admin, disappears from App availability, and restores as inactive;
- confirm existing history remains readable.

Verify:

- health readiness remains OK and no credential values appear in output or logs.

## Risks and Compatibility

- No schema migration: `disabled` is an existing allowed state.
- Existing locked jobs must resolve their stored revision even while the Provider is archived; only new-work selection is blocked.
- Current unrelated Android working-tree changes must remain untouched.

## Implementation Handoff

Start with Task 1, then implement Task 2 before Web UI work. Run focused verification after each task and the integrated smoke only after contract, Backend, and Web tests pass.
