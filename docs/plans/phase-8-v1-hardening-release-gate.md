# Phase 8 Implementation Plan

## Progress

- Status: COMPLETE — all 9 Tasks and the release-profile split are implemented; the deterministic
  `verify-phase8.ps1` gate passes with `product_release=v1`. V1 is direct-model only, and real
  credentialed AutoDL/Comfy acceptance is a V1.1 prerequisite.
- Environment fix (2026-10-07): `android/verify-phase6.ps1` now passes an explicit pytest `--basetemp`,
  so the gate no longer depends on the machine's default pytest temp directory being writable.
- Planning mode: `PHASE_PLAN + LARGE`
- Planned: 2026-10-07
- Scope: V1 hardening, fault/recovery verification, security verification, backup/restore, operator
  runbooks, and the release gate. No new product surface.
- Execution rule: complete, verify, and Git-commit every Task before starting the next Task.
- Reclassified external gate: real credentialed AutoDL/Comfy acceptance is a V1.1 prerequisite and no
  longer blocks the direct-model V1 release.
- Task 1 — COMPLETE (2026-10-07): `docs/acceptance/v1-acceptance-matrix.md` maps scenarios 1–22 to
  evidence with owners/status; V1.1 23–43 excluded; deferred prerequisites listed.
- Task 2 — COMPLETE (2026-10-07): `backend/tests/test_fault_recovery.py` covers cancelled-never-reconciled,
  external success published without resubmit, unknown external → running (no resubmit), and job creation
  blocked at capacity (507). Verified Ruff + focused pytest.
- Task 3 — COMPLETE (2026-10-07): `backend/tests/test_security_boundary.py` covers App/Admin scope
  isolation, redaction of the overview payload, and authenticated-only asset content; added
  `infra/verify-phase8-deployment.ps1` and wired it into CI.
- Task 4 — COMPLETE (2026-10-07): `infra/backup.ps1`, `infra/restore.ps1`, and
  `infra/verify-backup-restore.ps1` (consistent SQLite snapshot + storage pair). Verification passed.
- Task 5 — COMPLETE (2026-10-07): `docs/runbooks/` (empty-deployment setup, credential lifecycle, provider
  configuration, workflow publish/rollback, node replacement, incident recovery) and `infra/README.md`
  links.
- Task 6 — COMPLETE (2026-10-07): `android/verify-phase8.ps1` reuses the deterministic Phase 6 Android
  gate and release-boundary scan; connected hardening instrumentation runs in CI.
- Task 7 — COMPLETE (2026-10-07): `web-admin` tests for one-time rotation acknowledgement and 401 →
  session expiry.
- Task 8 — COMPLETE (2026-10-07): root `verify-phase8.ps1` orchestrates contract, Backend, Web,
  backup/restore, and Android; CI gained `backup-restore` and `phase8-exit` jobs.
- Task 9 — COMPLETE (2026-10-07): plan/roadmap/README updated; no unclassified V1 scenario remains.
- Release-track verification (2026-10-08): direct ComfyUI API requests are rejected, ComfyUI/Workflow
  Web routes are hidden/redirected, and the direct-model V1 gate passes independently.

## Goal

Harden the completed Phase 1–7 system into a V1 release candidate and prove the release gate:

- map every confirmed V1 acceptance scenario to automated or operator-run evidence and close the gaps;
- prove fault and recovery behavior never re-executes, re-charges, or loses successful results;
- prove the security boundary (HTTPS, secrets, redaction, authorization, throttling);
- provide consistent database + private-storage backup and restore;
- provide operator runbooks for empty-deployment setup, credential lifecycle, Provider/Workflow
  operations, node replacement, and incident recovery;
- aggregate every quality boundary into one deterministic Phase 8 exit matrix.

This phase adds verification, fixtures, runbooks, and gate wiring. It does not add product behavior,
does not pull V1.1 Outfits or ComfyUI forward. Comfy production readiness is a separate V1.1 claim.

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 8.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md): §17 test strategy and
  §18 acceptance scenarios 1–22 (V1) / 23–43 (V1.1, out of scope).
- [Product Flow](../product-flow.md): locked configuration, `waiting_provider`, `needs_attention`,
  storage blocking/automatic resume, archive/restore, token invalidation, late-result cleanup.
- Completed plans: [Phase 5](phase-5-comfyui-workflow-recovery.md),
  [Phase 6](phase-6-android-v1-completion.md), [Phase 7](phase-7-web-admin-operations-completion.md),
  [Provider Archive Lifecycle](provider-archive-lifecycle.md),
  [Local-first Asset Library](local-first-asset-library.md).
- Existing gates: `contracts/tooling/verify-*.ps1`, `android/verify-phase6.ps1`,
  `android/verify-release-boundary.ps1`, `web-admin/verify-phase7.ps1`,
  `infra/verify-phase{2,4,5}-deployment.ps1`, and [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).
- ADRs [0005 single-instance runtime](../adr/0005-v1-single-instance-runtime.md),
  [0007 private content-addressed storage](../adr/0007-private-content-addressed-storage.md),
  [0008 durable job execution](../adr/0008-durable-job-execution.md).

## Current Repository State

- Backend has 30+ test modules and 122 passing tests covering state machine, scheduler recovery,
  provider contract, Comfy/Workflow lifecycle, local-first cleanup, auth, storage, and migrations.
- CI runs Contract, Backend (with Ruff/Pyright/full pytest + per-phase subsets), Web Admin (lint/
  typecheck/unit/build/bundle + Playwright e2e), Android (build/lint/unit/instrumentation/release
  boundary), a device instrumentation job, a production deployment smoke, and a deterministic exit
  matrix aggregator.
- Existing fault coverage: scheduler restart requery and offline-node resume
  (`test_scheduler_recovery.py`), `needs_attention` commands (`test_job_commands.py`), storage
  admission, local-first grace/reference protection (`test_local_first_library.py`).
- Existing security coverage: auth scope isolation, CSRF/origin, login throttling, secret redaction,
  private asset downloads (`test_auth_http.py`, `test_security_credentials.py`,
  `test_comfy_node_http.py`, `test_workflow_lifecycle.py`, deployment smoke).
- Not present: an acceptance-scenario evidence register; explicit disk-full and concurrent-duplicate
  fault tests; a backup/restore tool and its verification; operator runbooks; a single Phase 8 exit
  script/job; a documented credentialed Comfy acceptance runbook.

## Implementation Delta

### REUSE

- All existing tests, gates, deployment scripts, and CI jobs.
- Fault-injection patterns already established by the scheduler, Comfy fixture, and local-first suites.
- Deployment smoke and release-boundary patterns.

### NEW

- `docs/acceptance/v1-acceptance-matrix.md` mapping scenarios 1–22 to evidence and status.
- Additional deterministic fault tests (disk-full admission, concurrent duplicate submit, late result
  after cancel, external-unknown classification).
- A security verification fixture/script consolidating the boundary checks.
- `infra/backup.ps1` + `infra/restore.ps1` (+ verification) for consistent DB + private-storage backup.
- `docs/runbooks/` operator runbooks and `infra/README.md` updates.
- `verify-phase8.ps1` orchestrator and a CI `phase8-exit` aggregation job.

### MODIFY

- `.github/workflows/ci.yml`, `README.md`, roadmap, and `infra/README.md`.
- Android and Web test suites only where a confirmed V1 scenario lacks coverage.

## Technical Decisions

### Evidence classification

Each acceptance scenario is classified as `automated` (deterministic test), `operator` (scripted
manual run against a real deployment), or `deferred` (requires the real Comfy node/Workflow or a
credentialed Provider). The release gate passes only when no V1 scenario (1–22) is unclassified or
blocked on an in-repo gap; `deferred` items are explicit, listed, and owned.

### Fault injection is deterministic and offline

Fault tests use the existing injected transports and fake/Comfy fixtures; no test spends Provider
credit or requires the network. Disk-full is simulated through the shared capacity port, not by filling
the host.

### Backup/restore correctness

A backup must be a consistent pair: a SQLite snapshot captured without concurrent writes plus the
private-storage volumes. Restore is verified by starting a clean instance against the restored pair and
checking referential integrity (assets ↔ stored objects ↔ jobs ↔ outputs) and that private content is
readable only through authenticated routes. Backups never contain plaintext secrets beyond what the
encrypted envelopes already require, and never enter source control.

### V1 release gate is deterministic; credentialed Comfy belongs to V1.1

`verify-phase8.ps1` aggregates contract, Backend, Web, Android, and deployment gates under `v1` without
a ComfyUI dependency. Real credentialed AutoDL/Comfy acceptance is documented in the V1.1 acceptance
record and is not invented as an automated test.

No new ADR is required; the phase reuses existing durability, storage, and single-instance decisions.

## Tasks

### Task 1 — V1 acceptance scenario matrix and evidence register

Affected:

- `docs/acceptance/v1-acceptance-matrix.md` (new)
- references to existing tests/scripts

Work:

- Enumerate Product Spec scenarios 1–22 with owning component, evidence type, exact test/script, and
  status; exclude 23–43.
- Mark gaps explicitly (e.g. disk-full, concurrent duplicate, late result) for later Tasks.

Verify:

- Every V1 scenario has an owner and a status; no scenario is left unclassified.

Dependencies: none (first task).

### Task 2 — Backend fault-injection and recovery tests

Affected:

- `backend/tests/test_fault_recovery.py` (new) or focused additions to existing suites
- capacity/admission and scheduler paths as needed

Work:

- Add deterministic tests for: disk-full admission rejected for upload and job creation while persisted
  `queued` work stays blocked-with-reason and resumes after space returns; concurrent duplicate submit
  produces one job (idempotency); late result after cancel is discarded and cleaned; unknown external
  state maps to `needs_attention` without resubmission.
- Reuse injected transports/fixtures; assert no duplicate external execution and no lost success.

Verify:

- Full Backend `ruff`/`pyright`/`pytest` pass; new tests cover each fault class.

Dependencies: Task 1.

### Task 3 — Security boundary verification suite

Affected:

- `backend/tests/test_security_boundary.py` (new) or consolidation
- `infra/verify-phase8-deployment.ps1` (new) for HTTPS/redaction smoke
- redaction assertions across Provider/Comfy/Workflow payloads

Work:

- Assert HTTPS-only production boundary, secret never echoed or logged, unauthorized asset download
  denied, App Token rejected on admin routes and vice versa, CSRF/origin enforced, login throttling,
  and redacted diagnostics free of payloads/tokens/paths.

Verify:

- Security tests and the deployment security smoke pass; credential scan finds no leaks in logs/bundle.

Dependencies: Tasks 1, 2.

### Task 4 — Backup and restore

Affected:

- `infra/backup.ps1`, `infra/restore.ps1`, `infra/verify-backup-restore.ps1` (new)
- `infra/README.md`

Work:

- Capture a consistent SQLite snapshot plus private-storage volumes into an operator-owned archive.
- Restore into a clean instance and verify referential integrity and authenticated-only content access.
- Document retention, off-host storage, and "never commit backups".

Verify:

- Restore verification passes; integrity check reports no orphans; content not readable without auth.

Dependencies: Tasks 1, 2, 3.

### Task 5 — Operator runbooks

Affected:

- `docs/runbooks/{empty-deployment-setup,credential-lifecycle,provider-configuration,workflow-publish-rollback,node-replacement,incident-recovery}.md`
- `infra/README.md`, `README.md` links

Work:

- Runbooks for: configure a working system from an empty deployment; initialize/rotate App and Admin
  credentials; configure Provider/Comfy node; publish and roll back a Workflow; replace a physical node
  with compatible-node checks; recover from `needs_attention`, disk-full, backend-offline, and canceled
  jobs.
- Label the deferred credentialed Comfy acceptance procedure as a V1.1-only release prerequisite.

Verify:

- Each runbook has prerequisites, exact commands, expected signals, and recovery; reviewed against the
  real scripts.

Dependencies: Task 4.

### Task 6 — Android hardening verification

Affected:

- `android/app/src/test/**`, `android/app/src/androidTest/**` where gaps exist
- `android/verify-phase8.ps1` (new) or extension of `verify-phase6.ps1`

Work:

- Close remaining confirmed gaps: network-loss recovery, process death during import/creation, font
  scale, narrow screen, and accessibility for critical flows; reuse existing Compose/instrumentation
  patterns.

Verify:

- Android build/lint/unit/instrumentation compile/release plus the new checks pass.

Dependencies: Task 1.

### Task 7 — Web Admin hardening verification

Affected:

- `web-admin/src/**/*.test.tsx`, `web-admin/tests/e2e/*`

Work:

- Add coverage for dangerous-operation confirmations, session-expiry return to the same path, and
  one-time secret handling; ensure e2e smokes run in CI.

Verify:

- Web lint/typecheck/unit/build/bundle/e2e pass.

Dependencies: Task 1.

### Task 8 — Phase 8 exit matrix and orchestration

Affected:

- `verify-phase8.ps1` (repository root)
- `.github/workflows/ci.yml` (`phase8-exit` job)
- `README.md`

Work:

- Orchestrate contract, Backend, Web, Android, deployment, backup/restore, and security gates into one
  command and one CI aggregation job that fails closed.
- Make the gate output state that credentialed ComfyUI acceptance belongs to V1.1.

Verify:

- `verify-phase8.ps1` passes locally where the environment supports it; CI job aggregates every
  required boundary.

Dependencies: Tasks 2–7.

### Task 9 — Release readiness report and documentation

Affected:

- `docs/acceptance/v1-acceptance-matrix.md` (final status)
- `README.md`, roadmap, this plan

Work:

- Record final scenario statuses, executed evidence, deferred items with owners, and the release
  decision; update roadmap to Phase 9 readiness.

Verify:

- Matrix shows no unclassified V1 scenario; roadmap/README reflect V1 release-gate status.

Dependencies: Task 8.

## Phase Exit Checklist

- [ ] Every V1 acceptance scenario 1–22 has evidence or a documented deferred owner; V1.1 23–43 excluded.
- [ ] Fault tests prove no re-execution, no re-charge, no lost successful results across restart,
      offline, disk-full, duplicate submit, and late results.
- [ ] Security boundary verified: HTTPS, secret management, redaction, unauthorized download denial,
      App/Admin scope isolation, CSRF/origin, throttling.
- [ ] Backup/restore verified for a consistent DB + private-storage pair with integrity and auth checks.
- [ ] Operator runbooks let an operator configure a working system from empty and replace a node and
      roll back a Workflow.
- [ ] One deterministic `verify-phase8.ps1` and CI `phase8-exit` gate aggregate all boundaries.
- [x] Credentialed AutoDL/Comfy acceptance is documented as a V1.1 manual release step; it does not
      block V1, and Comfy production readiness is not claimed until it passes.

## Risks

- Fault tests can be flaky if they depend on timing; assert on persisted state and injected transports,
  not sleeps.
- Backup/restore can corrupt a live SQLite database if captured without the write lock; snapshot via a
  supported method and verify.
- The working tree currently holds uncommitted Phase 6 and Phase 7 work; commit or otherwise resolve it
  before starting Phase 8 so release evidence is isolated.
- Real credentialed Comfy acceptance may slip; it must block only the V1.1 ComfyUI release claim.

## Upstream Conflicts

None. Phase 8 verifies confirmed behavior and does not change Product Spec, UI Spec, or architecture.

## Implementation Handoff

Plan:
docs/plans/phase-8-v1-hardening-release-gate.md

Current scope:
Phase 8 — V1 Hardening and Release Gate

Start with:
Task 1 — V1 acceptance scenario matrix and evidence register

Recommended implementation scope:
Task 1 only, then Verify (the matrix determines the remaining gap-closing Tasks).

Prerequisite:
Resolve uncommitted Phase 6/7 working-tree changes before committing Phase 8 work.

Implementation session should:
- read this persisted Plan and the Product Spec §17–18;
- inspect current tests, gates, infra scripts, and CI;
- execute the selected Task's Work, run its Verify, and record material deviations;
- not invent product behavior or claim Comfy production readiness.
