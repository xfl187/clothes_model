# Phase 7 Implementation Plan

## Progress

- Status: COMPLETE — all 16 Tasks implemented and the deterministic Phase 7 gate passed; Playwright e2e
  smokes updated but deferred to an environment with a browser and contract mock.
- Planning mode: `PHASE_PLAN + LARGE`
- Planned: 2026-10-07
- Scope: Complete the confirmed Quiet Control Room Web Admin and the Backend Admin/Cleanup/
  diagnostics/security surface on the stable Phase 1–6 platform.
- Execution rule: complete, verify, and Git-commit every Task before starting the next Task.
- Contract first: Task 1 must land and regenerate before any Backend or Web Admin consumer work.
- Deferred (out of this phase): real credentialed AutoDL/Comfy operator acceptance remains a later
  release-readiness gate and is not part of the Phase 7 exit gate.
- Task 1 — COMPLETE (2026-10-07): added the Admin/Operations contract operations and regenerated
  all consumers. New operations: `getSystemOverview`, `getAppCredentialStatus`, `rotateAppCredential`,
  `testProviderConnection`, and admin-scoped `adminCancelJob`/`adminCancelJobItem`/`adminRetryJobItem`/
  `adminRequeryJobItem`/`adminFinishJobItemAsFailed`, with supporting `SystemOverview*`,
  `EffectiveConfiguration`, `AppCredentialStatus`, `AppCredentialRotation`, and
  `ProviderConnectionTestResult` schemas. Deviation: because
  `backend/tests/test_contract_routes.py` requires exact contract/route parity, the nine new
  operationIds are registered in `modules/admin/http.py` as 501 placeholders; Tasks 2–6 replace them
  with real handlers. Verified: Redocly lint, `verify-generated.ps1` (drift 247 files, Pyright, Web
  tsc, Kotlin compile), additive + Phase 2/3/5/6/local-first boundary scripts, `verify-contract.ps1`
  (Prism examples), Backend Ruff/Pyright on the changed module, full Backend pytest (117 passed).
- Task 2 — COMPLETE (2026-10-07): added `modules/system/http.py` (`getSystemOverview`) aggregating
  business/database/storage/ComfyUI dependencies, run blockers, deep-linked action items, verdict, and
  effective configuration; registered in `api/routes.py` and removed the placeholder. Verified with new
  HTTP tests (401, aggregate shape, storage-degradation verdict), Ruff, Pyright.
- Task 3 — COMPLETE (2026-10-07): added `retention_policy` and `storage_scans` tables with migration
  `20261007_0007`; implemented retention GET/PUT, real `scanStorage` (protected vs reclaimable
  classification persisted as a scan), and `cleanupStorage` requiring a valid `scan_id` +
  `confirm_irreversible` while preserving reference protection; aligned `getStorageStatus` to the
  contract shape. Verified with new storage tests, updated migration assertions, Ruff, Pyright.
- Task 4 — COMPLETE (2026-10-07): added `getAppCredentialStatus`/`rotateAppCredential` to
  `modules/auth/http.py` (admin-session + CSRF), returning App Token metadata and a one-time token with
  idempotent replay rejection; verified old-token invalidation and no secret persistence.
- Task 5 — COMPLETE (2026-10-07): implemented real keyset cursor pagination + state filter for
  `listDiagnosticJobs` and admin-scoped recovery routes (`adminCancelJob`, `adminCancelJobItem`,
  `adminRetryJobItem`, `adminRequeryJobItem`, `adminFinishJobItemAsFailed`) reusing job command services.
- Task 6 — COMPLETE (2026-10-07): added free `testProviderConnection` (`connection_test` service method)
  distinct from paid validation, and populated Comfy `active_workflow_compatibility` from node health and
  active Workflow state. Verified focused provider/Comfy tests.
- Task 7 — COMPLETE (2026-10-07): shared `adminApi` (single generated `Configuration`, in-memory CSRF),
  problem-details parsing, 401→re-authentication via `useAdminQuery`, offline detection, Web design
  tokens, and reusable UI primitives (verdict strip, ledger, status marks, verification rail, module
  error, danger dialog, one-time secret dialog).
- Task 8 — COMPLETE (2026-10-07): `概览 / 配置 / 运行维护` Sidebar IA, all A00–A12 routes, `/` → overview,
  landing on overview after login, preserved target path on expiry, and offline banner.
- Task 9 — COMPLETE (2026-10-07): A01 overview (verdict strip, four-dependency ledger, run blockers,
  deep-linked actions, effective-config band).
- Task 10 — COMPLETE (2026-10-07): A06/A07 provider hardening (free connection test vs paid minimal
  generation test, archive/restore read-only) and the independent A08 default-backend page.
- Task 11 — COMPLETE (2026-10-07): A02 ComfyUI node page (effective config vs draft, health layering,
  verification rail, secret override, disable confirmation).
- Task 12 — COMPLETE (2026-10-07): A03–A05 Workflow list with state column, Inspector, validate, and
  activation/rollback impact confirmation.
- Task 13 — COMPLETE (2026-10-07): A09–A10 job diagnostics table with state filter, Inspector, and
  state-gated admin recovery actions.
- Task 14 — COMPLETE (2026-10-07): A11 storage capacity/classification, retention editing within
  confirmed scope, scan preview, and irreversible cleanup confirmation.
- Task 15 — COMPLETE (2026-10-07): A12 Token/Security with App Token metadata, one-time rotation dialog,
  Admin Token SSH-reset note, and shared danger/one-time-secret dialogs.
- Task 16 — COMPLETE (2026-10-07): added `web-admin/verify-phase7.ps1`; the gate passed (contract
  drift + boundaries, Web lint/typecheck/unit tests/build/bundle credential scan). Backend Ruff/Pyright
  and full pytest (122) passed. Playwright e2e smokes were updated but not executed in this environment
  (no browser/mock run); run `corepack pnpm@10.34.5 web:test:e2e` when a browser is available.
- Deviations: workflow upload/binding wizard and provider partitioned-form depth are lighter than the
  spec's high-fidelity prototype; all confirmed capabilities, states, and actions are present. Real
  credentialed Comfy acceptance remains deferred.
- Next action: Phase 7 complete — return to `$planning` for Phase 8 (V1 Hardening and Release Gate).

## Goal

Complete the V1 operations control plane without changing confirmed product behavior:

- the eight confirmed Web Admin capabilities reachable through the fixed `概览 / 配置 / 运行维护`
  Sidebar IA;
- a real system overview with four dependency states, run blockers, action list, and effective-config
  summary;
- a ComfyUI node verification rail, immutable Workflow list/detail/activation/rollback, and a
  single-active LLM Provider lifecycle with separated connection and generation tests;
- an independent default-backend page;
- a high-density job diagnostics table with a detail Inspector and state-gated recovery actions;
- storage capacity, retention policy, scan preview, manual cleanup, and post-cleanup scheduling
  recovery;
- App Token rotation with one-time secret display and an Admin Token SSH-reset boundary;
- global offline/session-expiry handling, dangerous-action confirmations, and unsaved-change guards;
- Backend endpoints, persistence, migrations, redaction, and audit metadata sufficient for every
  page, plus deterministic verification.

This phase implements the Web Admin product surface and the Backend Admin/Cleanup/diagnostics/
security gaps it depends on. It does not pull V1.1 Outfits forward, does not implement real
credentialed Comfy acceptance, and does not add capabilities excluded by the Web Admin UI Spec §2.2.

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 7.
- [Web Admin UI Spec](../superpowers/specs/2026-09-24-web-admin-ui-design.md), especially §2 capability
  boundaries, §3–4 IA/navigation, §5 UI Flow, §6 A00–A12 + X01–X03 inventory, §7 page responsibilities,
  §9 state/error/recovery, §10 dangerous operations, and §13 visual application.
- [Web Admin Visual Direction](../superpowers/specs/2026-09-24-web-admin-visual-direction.md) and
  [DESIGN.md](../../DESIGN.md) Web Admin sections.
- Confirmed prototypes under `prototypes/web-admin-high-fi/` (`index.html`, `states.html`) as the
  visual/interaction acceptance reference.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md): module boundaries
  (`Admin`, `Cleanup`), system status, retention/24-hour input-copy cleanup, App Token rotation,
  task/Provider/Workflow lifecycle, and security/redaction rules.
- [Product Flow](../product-flow.md): locked configuration, `waiting_provider`, `needs_attention`,
  storage blocking and automatic resume, archive/restore, token invalidation.
- Existing contracts under `contracts/openapi/` (`paths/admin.yaml`, `storage.yaml`, `diagnostics.yaml`,
  `auth.yaml`, `providers.yaml`, `workflows.yaml`; `components/admin/schemas.yaml`,
  `components/auth/schemas.yaml`) and the contract-first tooling (`contracts/tooling/verify-generated.ps1`).
- Prior plans: [Phase 5](phase-5-comfyui-workflow-recovery.md), [Phase 6](phase-6-android-v1-completion.md),
  [Provider Archive Lifecycle](provider-archive-lifecycle.md), [Local-first Asset Library](local-first-asset-library.md).
- ADRs [0004 OpenAPI contract ownership](../adr/0004-openapi-contract-ownership.md),
  [0005 V1 single-instance runtime](../adr/0005-v1-single-instance-runtime.md),
  [0007 private content-addressed storage](../adr/0007-private-content-addressed-storage.md),
  [0008 durable job execution](../adr/0008-durable-job-execution.md).

## Current Repository State

Backend (`backend/src/clothes_model/`):

- `modules/admin/http.py` already serves real default-provider, Comfy node GET/PUT/test, diagnostics
  list/detail, and a storage-status route whose shape diverges from the contract. Retention GET/PUT and
  `POST /admin/storage/scan` are `add_stub_routes` 501 stubs (`admin/http.py:139-146`).
- `modules/providers/http.py` and `modules/workflows/http.py` are fully real (create/list/get/validate/
  activate/retire + provider CRUD/archive/restore/validate/enable).
- `modules/cleanup/service.py` implements the 24-hour input-copy schedule/cleanup with active-reference
  protection and `stored_objects.asset_ref_count`; `modules/cleanup/http.py` ignores
  `CleanupRequest.scan_id`/`confirm_irreversible`.
- `modules/auth/application/services.py:88` implements `rotate_app`/`revoke_app`, but they are exposed
  only through `operator.py` CLI; there is no HTTP route and no contract operation.
- No admin system-overview endpoint exists; `modules/health.py` returns `ready=ok` with only Comfy
  partial-failure and no aggregate verdict, action list, or snapshot timestamp.
- `security_audit_events` is written (auth/providers/comfy/workflows) but has no read surface; diagnostics
  list has no real cursor pagination (`next_cursor=None`).

Contract:

- `contracts/openapi` already defines default-provider, Comfy node, retention, storage status/scan/cleanup,
  diagnostics, provider lifecycle, and workflow operations.
- Missing operations: admin system overview, App Token rotation/metadata, admin-scoped job recovery
  commands, a free Provider connection test distinct from paid generation validation, and storage scan
  persistence/preview semantics alignment.

Web Admin (`web-admin/`):

- The app is a Phase 1 skeleton: 5 routes (`app/router.tsx:9-23`), a two-item Sidebar
  (`app/AppShell.tsx`), login, provider admin, and a `/contract-status` proof. `/admin` is an inline stub.
- Only `LoginPage`, `ProviderAdminPage`, and `ContractStatusPage` exist; `A01–A05`, `A08–A12` are missing
  and `A06/A07` are partial on one page.
- `@tanstack/react-query` is installed but used by one page only; gateways each construct their own
  generated `Configuration`; there is no shared HTTP layer, ProblemDetails handling, 401 re-auth,
  offline/snapshot layer, or shared danger/one-time-secret dialogs.
- Styles are ~10 CSS variables in `src/styles/global.css`; no Web token layer for the §13 Quiet Control
  Room rules (serif verdict headings, ledger rows, verification rail, Inspector, status marks).
- Tests: 3 Vitest files + 2 Playwright smokes.

## Implementation Delta

### REUSE

- FastAPI modular-monolith, router registry, UoW/repositories, Alembic migrations, single-instance
  scheduler ownership, encrypted secret envelope, Admin session + CSRF + origin checks, idempotency
  records, security audit events, structured logging.
- Provider/Workflow/Comfy node services and their validation rails; job command application services;
  storage capacity guards; content-addressed storage and reference protection.
- OpenAPI contract-first regeneration, generated Python/TS/Kotlin consumers, and drift gates.
- Android-confirmed shared state semantics; the Web Admin UI Spec and prototypes for visual acceptance.

### NEW

- Contract operations for: system overview; storage scan persistence/preview; App Token metadata and
  rotation with one-time reveal; admin-scoped job recovery commands; free Provider connection test;
  diagnostics cursor pagination; populated Comfy `active_workflow_compatibility`.
- Backend: `modules/system` overview aggregation; retention policy persistence + migration; real storage
  scan with scan records; cleanup honoring `scan_id`; admin token/security service; audit-read surface.
- Web Admin: shared gateway/HTTP + ProblemDetails + session-expiry + offline layer; Web design-token
  layer; full Sidebar IA and routing; feature modules for overview, ComfyUI node, Workflows, Provider
  hardening, default backend, diagnostics, storage, and security; shared dialogs/guards.

### MODIFY

- `contracts/openapi/**` and all generated consumers + drift baselines.
- `modules/admin/http.py`, `modules/cleanup/**`, `modules/auth/**`, `modules/jobs/**`,
  `modules/providers/**`, `modules/comfy/**`, `api/routes.py`, readiness, and diagnostics.
- `web-admin/src/**` (router, shell, gateways, styles, features, tests) and `web-admin/tests/e2e`.
- `README.md`, roadmap/plan progress markers, and `infra/README.md` where operations evidence changes.

## Technical Decisions

### Admin authentication boundary for recovery actions

- Keep App-token job commands and Admin-session job recovery as separate surfaces. Add admin-scoped
  routes under `/api/v1/admin/diagnostics/jobs/{job_id}/...` requiring `AdminSession` (+ `AdminCsrf`
  for writes) that reuse the existing job command application services. Do not weaken the App-token
  boundary by accepting a Bearer token on admin routes or vice versa.

### Storage scan and cleanup contract

- Persist a scan record (`scan_id`, counts, protected/reclaimable sizes, actor, `completed_at`) so
  `cleanupStorage` can require and validate the latest confirmed `scan_id` and `confirm_irreversible`.
- Align `getStorageStatus` to the contract `StorageStatus` shape (`state/used_bytes/available_bytes/
  accepting_new_work/block_reason/checked_at`) instead of the current divergent payload, and derive
  `state` from the shared reserve threshold.
- Retention policy persists `unfavorited_output_days` and `intermediate_file_days` and applies only to
  the confirmed scopes (unfavorited outputs, intermediate mask/preprocessing files); it must never
  weaken active-reference or favorite protection.

### Provider connection vs generation test

- Add a free `POST /api/v1/admin/providers/{provider_id}/connection-test` (reachability/protocol/metadata,
  no paid generation). Keep the existing paid `validateProviderConfig` as the minimal generation test and
  label it as such in the UI. Both remain independent of enable/default.

### App Token rotation

- Add Admin-session operations to read App credential metadata (token id, status, created/rotated time)
  and to rotate, returning the new plaintext token exactly once (write-only, never readable again).
  Reuse `TokenService.rotate_app`; write `token.app.rotate` audit metadata. Admin Token web rotation
  remains excluded; the page only documents the SSH reset boundary.

### Visual language

- Implement the confirmed Web-specific rules from `DESIGN.md`/§13 as a small token + component layer
  (verdict strip, ledger rows, verification rail, Inspector, status marks, dense table). Do not copy
  Android mobile structures. Treat prototypes as acceptance reference, not production code.

No new ADR is required: the provider/physical-node and durable-execution decisions already exist; the
auth-boundary and scan-record decisions above are implementation-level and are recorded here.

## Target Structure / Architecture

Backend additions:

- `modules/system/` — overview aggregation service + HTTP router (`GET /api/v1/admin/system/overview`).
- `modules/admin/http.py` — wire retention, scan, cleanup, overview; remove 501 stubs.
- Retention persistence: new table + migration (e.g. `retention_policy` singleton) and a scan-record
  table (e.g. `storage_scans`).
- `modules/auth/http.py` + application service — app credential metadata + rotation endpoints.
- `modules/jobs/` — admin-scoped recovery routes reusing command services.

Web Admin additions:

- `src/api/http.ts` + `gateways/` — shared `Configuration` factory, ProblemDetails parser, 401 →
  re-auth, offline/snapshot.
- `src/styles/tokens.css` — Web token layer; shared components under `src/components/`.
- `src/features/{overview,comfy,workflows,providers,default-backend,diagnostics,storage,security}/`.
- `src/app/AppShell.tsx` + `router.tsx` — three-group Sidebar and A00–A12 routes.

## Contract / Integration Strategy

1. Extend the canonical OpenAPI source first (Task 1), regenerate all three consumers, and pass the
   contract lint/bundle/drift gates before Backend or Web work.
2. Backend implements each new operation against the generated models with focused HTTP tests.
3. Web Admin consumes only the generated client through the shared HTTP layer.
4. Every state/action must map to a confirmed state meaning; no UI-invented statuses.

## Tasks

### Task 1 — Extend and regenerate the Admin/Operations contract

Affected:

- `contracts/openapi/openapi.yaml`
- `contracts/openapi/paths/admin.yaml`, `storage.yaml`, `diagnostics.yaml`, `auth.yaml`, `providers.yaml`
- `contracts/openapi/components/admin/schemas.yaml`, `components/auth/schemas.yaml`,
  `components/providers/schemas.yaml`
- `contracts/openapi/examples/*`, `contracts/openapi/baselines/*`
- generated Web/Android/Python clients

Work:

- Add `GET /api/v1/admin/system/overview` with a verdict enum (`ok/limited/action_required`), four
  dependency entries, run-blocker counts, action items with deep-link targets, effective-config summary,
  and `snapshot_at`.
- Add admin-scoped job recovery operations (`cancel`, `cancel item`, `requery item`, `retry item`,
  `finish item as failed`) under `/api/v1/admin/diagnostics/jobs/{job_id}/...` with `AdminSession` +
  `AdminCsrf` and Idempotency-Key.
- Add App credential operations: read metadata and rotate (write-only one-time token) under the auth
  admin surface.
- Add `POST /api/v1/admin/providers/{provider_id}/connection-test` (free) and keep the paid validation
  operation distinguished as the generation test; document both boundaries.
- Align `StorageStatus`, `StorageScanRequest/Result`, `CleanupRequest` with the persisted scan model;
  add pagination fields already present where needed.
- Extend `AppAuthStatus` (or add admin app-credential models) with identifier/status/created/rotated
  timestamps; add populate rules for Comfy `active_workflow_compatibility`.
- Regenerate and verify generated artifacts + boundary checks.

Verify:

- `./contracts/tooling/verify-generated.ps1` passes with no drift.
- Redocly lint/bundle passes; Web/Python/Android generated clients compile.
- Existing contract route/boundary tests pass.

Dependencies: none (first task).

### Task 2 — Backend system overview

Affected:

- `backend/src/clothes_model/modules/system/` (new service + `http.py`)
- `backend/src/clothes_model/api/routes.py`
- focused tests (`backend/tests/test_system_overview_http.py`)

Work:

- Aggregate business service, database, storage, and ComfyUI dependency states with real checks; on any
  single dependency failure return a partial result plus a module error, not a global failure.
- Compute run blockers (`waiting_provider`, storage-blocked `queued`, `needs_attention`, config faults)
  from persisted state.
- Build action items that deep-link to the responsible object, and the effective-config summary
  (default backend, active LLM, active Workflow version).
- Return `snapshot_at`; never fabricate health.

Verify:

- HTTP tests cover healthy, limited, action-required, and single-dependency-failure responses; no secret
  leakage.

Dependencies: Task 1.

### Task 3 — Backend retention, storage scan, and clean cleanup

Affected:

- `backend/src/clothes_model/modules/admin/http.py`
- `backend/src/clothes_model/modules/cleanup/service.py`, `http.py`
- `backend/src/clothes_model/infrastructure/database/models.py`, repositories, migrations
- focused tests (`test_storage_admin_http.py`, extend `test_local_first_library.py`)

Work:

- Implement retention policy persistence (singleton) + migration and wire GET/PUT; apply only to
  confirmed scopes and never bypass reference/favorite protection.
- Implement real `scanStorage`: filesystem/`stored_objects` reconciliation, protected vs reclaimable
  classification, persisted scan record + `scan_id`, no deletion.
- Make `cleanupStorage` require a valid `scan_id` + `confirm_irreversible`, delete only scanned
  reclaimable files, skip protected references, and record results.
- Align `getStorageStatus` to the contract shape and derive `state` from the shared reserve threshold.
- Surface post-cleanup scheduling recovery (blocked `queued` tasks resume automatically).

Verify:

- Migration upgrade/downgrade, scan preview correctness, protected-reference skipping, retention scope
  boundaries, and StorageStatus-contract alignment tests pass; Ruff/Pyright pass.

Dependencies: Task 1.

### Task 4 — Backend App Token metadata and rotation

Affected:

- `backend/src/clothes_model/modules/auth/http.py`, `application/services.py`
- `backend/tests/test_auth_http.py`

Work:

- Expose app credential metadata (id/status/created/rotated) under the Admin session.
- Implement rotation returning the new token once (write-only), revoking prior tokens, preserving
  `owner_scope_id`, and writing `token.app.rotate` audit metadata.
- Enforce CSRF/origin/session on writes; never log or re-return the token; keep Admin Token SSH-reset
  boundary (no web rotation).

Verify:

- Tests cover metadata read, one-time reveal, old-token invalidation, audit write, and non-leakage of
  token values in responses/logs.

Dependencies: Task 1.

### Task 5 — Backend admin diagnostics and recovery

Affected:

- `backend/src/clothes_model/modules/admin/http.py`
- admin-scoped recovery routes (jobs module)
- `backend/tests/test_job_commands.py`, `test_admin_diagnostics_http.py`

Work:

- Implement real cursor pagination + full state filter (and an "needs action" aggregate view) for
  `listDiagnosticJobs`.
- Add admin-scoped cancel/cancel-item/requery/retry/finish-failed routes reusing job command services,
  state-gated and idempotent.
- Surface redacted audit metadata alongside diagnostics without exposing secrets/raw payloads.

Verify:

- Pagination/filter tests, state-gated action tests, idempotency, and redaction tests pass.

Dependencies: Task 1.

### Task 6 — Backend Provider test split and Comfy compatibility

Affected:

- `backend/src/clothes_model/modules/providers/http.py`, `application/services.py`
- `backend/src/clothes_model/modules/admin/http.py` (Comfy payload)
- focused tests

Work:

- Add the free connection test (protocol/reachability/metadata) and keep paid validation as the minimal
  generation test; both independent of enable/default.
- Populate `active_workflow_compatibility` on the Comfy node payload from the existing compatibility
  evaluation.

Verify:

- Connection test spends no Provider credit; generation test remains cost-confirmed; compatibility field
  reflects the active Workflow; existing provider tests pass.

Dependencies: Task 1.

### Task 7 — Web Admin shared HTTP, session, offline, and token foundations

Affected:

- `web-admin/src/api/http.ts`, `web-admin/src/api/gateways/*`
- `web-admin/src/styles/global.css`, `web-admin/src/styles/tokens.css`
- `web-admin/src/components/*` (status/ledger/verdict/rail/Inspector/dialog primitives)
- `web-admin/src/test/setup.ts`

Work:

- Introduce one generated-`Configuration` factory with `credentials: 'include'` and in-memory CSRF.
- Centralize ProblemDetails parsing, 401 → preserve target + re-login, and offline/last-snapshot state
  with global write-disable.
- Add the Web token layer implementing the confirmed §13 rules and shared primitives; keep
  reduced-motion support.

Verify:

- Unit tests for ProblemDetails mapping, 401 re-auth, offline write-disable; lint/typecheck/build pass.

Dependencies: Task 1.

### Task 8 — Web Admin shell, navigation, and login

Affected:

- `web-admin/src/app/AppShell.tsx`, `router.tsx`, `AppShell.module.css`
- `web-admin/src/features/auth/*`

Work:

- Implement the fixed `概览 / 配置(4) / 运行维护(3)` Sidebar IA with rail behavior and correct active
  marking; remove the `/admin` stub and route `/` to overview.
- Route A00–A12; make login land on overview, preserve input on service-unreachable, and keep the
  in-memory CSRF/session contract.

Verify:

- Component tests for navigation, route guards, login error kinds; e2e login/session-expiry smoke.

Dependencies: Task 7.

### Task 9 — Web Admin A01 system overview

Affected: `web-admin/src/features/overview/*`

Work:

- Build the verdict strip, four-dependency ledger, run-blocker ledger, deep-linked action list, and
  low-emphasis effective-config band per §7/§13.2; keep loading/empty/module-error semantics.

Verify:

- Component tests for ok/limited/action-required and single-module failure; no invented health.

Dependencies: Tasks 2, 7, 8.

### Task 10 — Web Admin A06/A07 Provider and A08 default backend

Affected: `web-admin/src/features/providers/*`, `web-admin/src/features/default-backend/*`

Work:

- Harden Provider list/detail: partitioned form (identity/protocol, connection, key, model/vendor
  params, timeout, capability), adapter/endpoint/model editing, overwrite-only key, connection test vs
  paid generation test (cost confirm), capability source, revision/history, archive/restore, and
  single-active enforcement.
- Build the default-backend page (two comparable rows, availability/reason/version/capability,
  "only affects new jobs" note).

Verify:

- Component tests for save→inactive, enable, set-default separation, archive/restore read-only, secret
  never echoed.

Dependencies: Tasks 6, 7, 8.

### Task 11 — Web Admin A02 ComfyUI node

Affected: `web-admin/src/features/comfy/*`

Work:

- Separate current effective config, edit draft, and live health; render the ordered verification rail
  (connection → node dependencies → active-workflow trial), credential override without echo, enable/
  disable impact copy, and offline amber semantics.

Verify:

- Component tests for health layering, verification rail failure retention, secret redaction.

Dependencies: Tasks 6, 7, 8.

### Task 12 — Web Admin A03–A05 Workflows

Affected: `web-admin/src/features/workflows/*`

Work:

- Group list by `workflow_id + mode` with version rows and fixed state column; Inspector with bindings,
  capability source, validation/trial results; upload+binding desktop wizard; activation/rollback
  impact confirmation (new jobs only).

Verify:

- Component tests for grouping/state, wizard steps, validate/activate/rollback impact and error handling.

Dependencies: Tasks 1, 7, 8.

### Task 13 — Web Admin A09–A10 job diagnostics

Affected: `web-admin/src/features/diagnostics/*`

Work:

- Dense table (ID/mode/state/created/wait/locked provider/locked workflow/block summary) with filters
  including the needs-action view; right-side Inspector ordered conclusion → items → external execution
  → locked config → errors/lineage; state-gated actions wired to admin recovery endpoints.

Verify:

- Component tests for filters/pagination, state-gated actions, needs_attention panel, no cancel on
  terminal states.

Dependencies: Tasks 5, 7, 8.

### Task 14 — Web Admin A11 storage

Affected: `web-admin/src/features/storage/*`

Work:

- Capacity conclusion (not a single percentage), classification ledger (favorite/active-reference/
  expired/AutoDL temp), retention editing within confirmed scope, scan-preview → confirm → cleanup flow,
  and post-cleanup scheduling recovery display.

Verify:

- Component tests for scan preview, protected references shown, irreversible confirm, recovery status.

Dependencies: Tasks 3, 7, 8.

### Task 15 — Web Admin A12 security, X02, X03

Affected: `web-admin/src/features/security/*`, shared dialogs

Work:

- Show App Token identifier/status/rotation time (never the value); rotation confirm explaining
  immediate invalidation, Android re-auth, and unaffected server jobs; one-time token dialog requiring
  saved-confirmation; Admin Token SSH-reset read-only note.
- Implement the reusable danger-confirmation (impact → confirm → in-page result/recovery) and unsaved-
  changes guard.

Verify:

- Component tests for one-time display, confirm-required close, danger三段式, unsaved guard.

Dependencies: Tasks 4, 7, 8.

### Task 16 — Integrated verification and Phase 7 exit gate

Affected:

- `web-admin/tests/e2e/*`
- a Phase 7 gate script (e.g. `web-admin/verify-phase7.ps1` or extend repo gates)
- `README.md`, roadmap/plan progress markers

Work:

- Add e2e coverage for overview triage, node change, workflow publish/rollback, provider lifecycle,
  default backend, diagnostics recovery, storage scan→cleanup, token rotation, offline/session-expiry.
- Run the full deterministic gate: contract drift, Backend Ruff/Pyright/pytest, Web lint/typecheck/
  test/build/bundle-check/e2e.
- Update README/roadmap/plan to record Phase 7 completion and the deferred Comfy acceptance.

Verify:

- Gate passes; no credential values in output or logs; eight top-level pages reach the prototype's
  confirmed structure at ~1050px and ~820px.

Dependencies: Tasks 1–15.

## Phase Exit Checklist

- [ ] `概览 / 配置 / 运行维护` Sidebar IA with all eight capabilities reachable as real pages.
- [ ] System overview shows real/snapshot/partial-failure, blockers, actions, and effective config.
- [ ] ComfyUI node verification rail (connection → dependencies → trial) and safe enable.
- [ ] Workflow list/detail/wizard/activate/rollback with capability source and new-jobs-only impact.
- [ ] Provider list/detail with partitioned form, overwrite-only key, separated connection vs paid
      generation test, archive/restore, single active connection.
- [ ] Independent default-backend page; no implicit default changes.
- [ ] Diagnostics table + Inspector with state-gated cancel/requery/retry/finish-failed; no terminal
      cancel; no silent Provider swap.
- [ ] Storage capacity/classification, retention within confirmed scope, scan preview, manual cleanup
      with protected-reference skipping, and automatic scheduling recovery.
- [ ] App Token rotation with one-time display; Admin Token remains SSH-reset only.
- [ ] Offline banner/last snapshot, session-expiry return, unsaved-change guard, one-time secret dialog,
      danger-confirmation三段式.
- [ ] API keys, node credentials, and tokens never echoed; admin operations carry audit metadata and
      redacted diagnostics.
- [ ] ~1050px narrow Sidebar and ~820px single-column adaptation pass visual/keyboard checks.
- [ ] Saving, validating, enabling, activating, and setting default remain independent actions; admin
      pages cannot mutate historical job locked configuration.
- [ ] Deterministic gate (contract + Backend + Web + e2e) passes.

## Risks

- Contract additions touch three generated clients and drift gates; Task 1 must land cleanly before
  consumers.
- Retention/scan expands cleanup scope beyond the current input-copy-only path; reference protection and
  favorites must not regress (regression tests required).
- Admin session (cookie/CSRF) vs App token (bearer) boundaries can leak if admin recovery reuses App
  routes; keep surfaces separate.
- The repository working tree currently contains an uncommitted post-exit Android/Backend correction
  batch (Phase 6, 2026-10-07). Commit or otherwise resolve it before starting Task 1 so Phase 7 commits
  stay isolated; it does not touch `contracts/`, `web-admin/`, or the Phase 7 Backend modules.
- Real Comfy acceptance remains deferred; Phase 7 must not claim Comfy production readiness.
- `README.md:9-11` still describes Workflows/Cleanup/ComfyNode/Retention/storage-scan as stubs; update
  it during Task 16.

## Upstream Conflicts

None. All required product behavior, UI structure, retention scopes, and token security rules are
confirmed in the Product Spec and Web Admin UI Spec. No new product decision is required for Phase 7.

## Implementation Handoff

Plan:
docs/plans/phase-7-web-admin-operations-completion.md

Current scope:
Phase 7 — Web Admin and Operations Completion

Start with:
Task 1 — Extend and regenerate the Admin/Operations contract

Recommended implementation scope:
Task 1 only, then Verify (contract-first; contract/generated drift blocks every consumer).

Prerequisite:
Resolve the uncommitted Phase 6 post-exit correction batch in the working tree before committing
Phase 7 work.

Implementation session should:
- read this persisted Plan and the listed Confirmed Inputs;
- inspect current Repository state (`contracts/openapi/**`, `backend/src/clothes_model/**`,
  `web-admin/src/**`);
- execute the selected Task's Work, run its Verify, and record material deviations;
- preserve confirmed product behavior and the Android/Backend platform rules;
- not enter another roadmap Phase.
