# Phase 9 Implementation Plan

## Progress

- Status: READY FOR IMPLEMENTATION (dependency: V1 release gate)
- Planning mode: `PHASE_PLAN + LARGE`
- Planned: 2026-10-07
- Scope: V1.1 分层穿搭 (Layered Outfit Track) as an independent domain module and independent Android
  entry, without changing V1 精准换装 behavior or its historical data.
- Execution rule: complete, verify, and Git-commit every Task before starting the next Task.
- Dependency: Phase 8 V1 release gate. The deterministic gate passed; the deferred credentialed
  AutoDL/Comfy acceptance is a release claim. Start Phase 9 only after the owner accepts the V1 release
  candidate, and never claim V1.1 production readiness ahead of the V1 release gate.
- Task 1 — COMPLETE (2026-10-07): additive V1.1 Outfit contract (13 operations, `OutfitSession`/
  `OutfitBranch`/`OutfitRevision`/`OutfitLayer`/`LayerTypeDefinition` schemas, job `outfit_context`),
  regenerated Web/Python/Android clients, and the V1 boundary scripts scoped so outfit resources are
  additive while V1 invariants stay enforced. Placeholder routes registered for contract/route parity.
  Verified: Redocly lint, `verify-generated.ps1`, additive/Phase 5 boundaries, `verify-contract.ps1`.
- Task 2 — COMPLETE (2026-10-07): `layer_type_definitions` (versioned, seeded with the four system
  types), `outfit_sessions`, `outfit_branches`, `outfit_revisions`, `outfit_layers` tables and migration
  `20261007_0008`; migration upgrade/downgrade tests and full Backend Ruff/Pyright/pytest pass.
- Task 3 — COMPLETE (2026-10-07): added the Outfits domain models, `SqlAlchemyOutfitRepository` (sessions,
  branches, revisions, layers, layer types, unfinished-job count) wired into the UoW, `OutfitService`
  (create/list/get/update/delete session, create/update/delete branch, mainline switching, deletion
  guards, contract payloads), and real HTTP handlers for the eight session/branch operations. Verified:
  new `test_outfits_http.py`, contract/route parity, full Backend Ruff/Pyright/pytest.
- Task 4 — COMPLETE (2026-10-07): real `addOutfitLayer` creates a linked single-garment job with
  capability/role gating (`sequential_layering`, `supported_layer_roles`) and a `pending_reapply` layer,
  and `selectOutfitRevision` commits an immutable revision only on explicit candidate selection (marking
  later layers `pending_reapply`); session creation now seeds a root revision as the base. Asset
  availability moved into the repository to respect the application-layer framework boundary. Verified:
  `test_outfits_layers.py` (job creation, select→revision, capability rejection), `test_architecture.py`,
  full Backend Ruff/Pyright/pytest.
- Task 5 — COMPLETE (2026-10-07): additive contract change exposing each branch's working-layer set;
  real `removeOutfitLayer` supporting `remove` (deletes the layer) and `revert` (invalidates), marking
  later layers `pending_reapply` and creating no task/fee; per-layer asset references. Verified:
  `test_outfits_layers.py` (remove/revert, no new jobs), regenerated clients, contract gates,
  `verify-generated.ps1`, full Backend Ruff/Pyright/pytest.
- Task 6 — PENDING
- Task 7 — PENDING
- Task 8 — PENDING
- Task 9 — PENDING
- Task 10 — PENDING
- Task 11 — PENDING
- Task 12 — PENDING
- Task 13 — PENDING
- Task 14 — PENDING
- Next action: implement Task 6 — Route switching (split ↔ dress) with new-branch creation and preserved
  compatible outerwear as `pending_reapply`.

## Goal

Add the confirmed V1.1 分层穿搭 experience on the stable V1 platform:

- an independent Android entry with a session list and a layered workbench that never changes the fixed
  V1 `首页 / 素材 / 历史` navigation;
- one session per original person image,逐件 adding garments and confirming each step;
- four system layer types `inner_top` / `outerwear` / `lower_body` / `dress` with a versioned layer
  definition set locked at session creation;
- immutable revisions, branches, revert, replace, remove, and `pending_reapply` after modifying a middle
  layer — with no automatic jobs or fees;
- split vs dress route switching that creates a new branch from the original person image;
- explicit compatible-Provider selection when a reapply's original Provider is unavailable, never a
  silent switch;
- outfit references participating in asset protection and cleanup;
- contract, persistence, jobs integration, Android UX, migration, and deterministic verification.

This phase adds a new domain module (`Outfits`) and optional job context. It must not alter V1 single-item
精准换装 semantics, its API behavior, or historical data.

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 9.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md): §2.3 V1.1 scope,
  §4.7 V1.1 flow, §9 data model (`OutfitSession`, `OutfitRevision`, `OutfitLayer`, `LayerTypeDefinition`),
  §10 retention/reference protection, and §18 scenarios 23–37.
- [Product Flow](../product-flow.md): V1.1 分层穿搭 flow, pending reapply, route switching, reference
  protection, and Provider capability gates.
- [Android UI Spec](../superpowers/specs/2026-09-23-android-v1-ui-design.md): §11 V1.1 extension boundary,
  the home mode card, the session list/workbench/branch-history/layer-management screens, and the reusable
  component boundary.
- V1 implementation plans and their verified evidence (Phases 6–8), plus ADR-0004 contract ownership,
  ADR-0005 single-instance runtime, ADR-0007 private storage.
- Existing capability contract already reserves `sequential_layering`, `supported_layer_roles`,
  `preserve_existing_garments`, and `outfit_context`.

## Current Repository State

- V1 Backend has the modular-monolith, UoW/Alembic, scheduler, Provider/Workflow planes, reference graph
  (`asset_references`, `stored_objects.asset_ref_count`), and cleanup.
- The OpenAPI contract intentionally excludes outfit resources; `verify-contract.ps1` and
  `verify-phase5-boundaries.ps1` currently **reject** `/api/v1/outfits` paths, and `TryOnJob` has no
  outfit context.
- Android has the fixed V1 navigation and reusable components explicitly designed for V1.1 reuse, with the
  V1.1 entry marked "即将开放".
- No `Outfits` tables, service, contract paths, or Android V1.1 screens exist.

## Implementation Delta

### REUSE

- Auth, assets/uploads, FileStorage, Provider capability model, durable job state machine and scheduler,
  retry/requery/recovery, reference protection, cleanup, generated-client and contract tooling.
- Android asset library/selector, job detail/result/compare components, draft/recovery patterns, and the
  bottom navigation (which must not change).

### NEW

- `Outfits` module: `OutfitSession`, `OutfitRevision`, `OutfitLayer`, versioned `LayerTypeDefinition`
  persistence, repositories, and application service.
- Outfit sessions, revisions, layers, branch and mainline management, `pending_reapply`, route switching,
  and reapply execution.
- Optional job outfit context and Provider capability/role gating at job creation.
- Outfit references in the asset reference graph and cleanup/protection rules.
- Android V1.1 entry, session list, workbench, layer management, branch history, and reapply flows.
- V1.1 contract operations, migration, tests, and a Phase 9 verification gate.

### MODIFY

- Contract (additive), generated clients, `api/routes.py`, job creation/validation, reference queries.
- The V1 contract boundary gates to permit the additive V1.1 Outfit surface while keeping V1 invariants.
- Android navigation entry (enable the V1.1 card) and Android V1.1 screens/state.

## Technical Decisions

### Separate module, additive contract

- Implement `Outfits` as an independent module. Outfit state never leaks into V1 UI or V1 job semantics.
- Add additive `/api/v1/outfits*` operations and an optional `outfit_context` on job creation. `TryOnJob`
  keeps every V1 field and behavior.
- The V1 boundary scripts currently assert the absence of outfit paths. Phase 9 must scope that assertion
  to the V1 surface (e.g. compare against a V1 baseline subset) rather than deleting the checks, so V1
  invariants remain enforced and the V1.1 surface is explicitly allowed.

### Versioned layer definitions

- `LayerTypeDefinition` is immutable and versioned. A session locks the definition-set version at
  creation; the four system types (`inner_top`, `outerwear`, `lower_body`, `dress`) are seeded. Adding
  types later must not require changing the `OutfitLayer` table shape.

### Revision and confirmation boundary

- A layer's generation is a single-garment `TryOnJob` linked to the session/revision/layer.
- A new immutable `OutfitRevision` is committed only when the user explicitly selects a candidate.
  Failed, cancelled, or `needs_attention` attempts never change the current confirmed revision.
- Modifying a middle layer regenerates from the nearest confirmed base revision and marks subsequent
  layers `pending_reapply`; reapply, replace, or remove each create no task until the user acts.

### Route switching and branches

- Switching split ↔ dress creates a new branch from the original person image, removes route-conflicting
  layers, and keeps compatible `outerwear` as `pending_reapply`. The original branch is unchanged and no
  task/fee is created by the switch itself.

### Provider gating, never silent

- Job creation for a layer requires a Provider that declares `sequential_layering` and supports the target
  layer role. Incompatibility blocks submission before persistence.
- Reapply prefills the original Provider/params but is always a new job. If unavailable/incompatible, the
  user must explicitly choose a compatible Provider and see the change; otherwise the layer stays
  `pending_reapply` and no job is created.

### Reference protection

- Outfit sessions, branches, confirmed revisions, and `pending_reapply` configurations are first-class
  references in `asset_references`. Protected assets cannot be deleted until the referencing outfit
  state is removed; deleting an outfit never cascades to shared assets or other branches.

No new ADR is required; this reuses existing durability, storage, and capability decisions. The boundary
gate scoping is an implementation-level change recorded here.

## Tasks

### Task 1 — Contract: Outfit surface, job outfit context, and boundary scoping

Affected:

- `contracts/openapi/openapi.yaml`, `paths/outfits.yaml` (new), `components/outfits/schemas.yaml` (new)
- `paths/jobs.yaml`, `components/jobs/schemas.yaml`, `components/providers/schemas.yaml`
- `contracts/tooling/verify-contract.ps1`, `verify-phase5-boundaries.ps1` (scope V1-only assertions)
- generated Web/Python/Android clients

Work:

- Add outfit session/revision/layer/layer-type operations (create session, get session, list sessions,
  add layer job, select candidate to commit revision, modify/remove/revert layer, create branch, set
  mainline, rename/favorite, delete session/branch, reapply).
- Add optional `outfit_context` to job creation and the capability/role gates.
- Scope the V1 boundary scripts so outfit resources are additive while V1 invariants stay enforced.
- Regenerate and verify.

Verify:

- `verify-generated.ps1` and `verify-contract.ps1` pass; V1.1 paths present and additive; V1 invariants
  still asserted; clients compile.

Dependencies: none (first task).

### Task 2 — Layer definitions, persistence, and migration

Affected:

- `backend/src/clothes_model/modules/outfits/domain/`, `infrastructure/`
- `backend/src/clothes_model/infrastructure/database/models.py`, repositories, UoW
- `backend/migrations/versions/<new>_v1_1_outfits.py`
- focused tests

Work:

- Add immutable versioned `LayerTypeDefinition` (body region, order, compatibility, conflicts, Provider
  capability requirements) with a seeded definition-set version for the four system types.
- Add `OutfitSession`, `OutfitRevision`, `OutfitLayer` tables with constraints and indexes; scope by
  `owner_scope_id`.

Verify:

- Migration upgrade/downgrade; seed idempotency; constraint tests; Ruff/Pyright.

Dependencies: Task 1.

### Task 3 — Outfit session, revision, and branch service

Affected:

- `backend/src/clothes_model/modules/outfits/application/`
- `backend/src/clothes_model/modules/outfits/http.py`, `api/routes.py`
- focused tests

Work:

- Create a session from one original person asset, locking the definition-set version.
- Manage main branch/revision, branch naming/favorite/mainline, and immutable revision lineage.
- Enforce "no delete while unfinished tasks exist" and "switch mainline before deleting the current
  branch; single branch deletes the whole session".

Verify:

- HTTP tests for lifecycle, branch/mainline rules, and deletion guards.

Dependencies: Task 2.

### Task 4 — Layer apply and confirmation boundary

Affected:

- `outfits` application service; jobs integration
- `backend/tests/test_outfits_layers.py`

Work:

- Add a layer by creating a linked single-garment `TryOnJob` carrying `outfit_context`
  (session/revision/layer/role).
- Commit a new `OutfitRevision` only when the user selects a candidate; keep unselected candidates.
- Reject incompatible Provider/role before job creation.

Verify:

- Tests for apply, capability rejection, candidate selection → new revision, and no state change on
  failure/cancel/`needs_attention`.

Dependencies: Tasks 3, 1.

### Task 5 — Modify, remove, revert, and `pending_reapply`

Affected:

- `outfits` service; reference/protection helpers
- focused tests

Work:

- Replace/remove/revert a layer, regenerating from the nearest confirmed base revision when the middle
  layer changes; mark subsequent layers `pending_reapply`.
- Ensure no task or fee is created until the user chooses reapply/replace/remove.

Verify:

- Tests proving subsequent layers become `pending_reapply`, old revisions/branches are preserved, and no
  jobs are created by the modification itself.

Dependencies: Task 4.

### Task 6 — Route switching (split ↔ dress)

Affected:

- `outfits` service; branch creation; layer conflicts
- focused tests

Work:

- Switch route by creating a new branch from the original person image, removing conflicting layers, and
  preserving compatible `outerwear` as `pending_reapply`.
- Keep the original branch intact; create no task or fee.

Verify:

- Tests for both switch directions, preserved outerwear, unchanged original branch, and zero created jobs.

Dependencies: Task 5.

### Task 7 — Reapply with explicit Provider selection

Affected:

- `outfits` service; job creation reuse
- focused tests

Work:

- Prefill original Provider/params; if unavailable/incompatible, require an explicit compatible Provider
  and surface the configuration change; record the actual locked version on the new job.
- When no compatible Provider exists, keep `pending_reapply` and explain, creating no job.

Verify:

- Tests for reapply success, explicit-switch path, and no-compatible-Provider path (no job created).

Dependencies: Task 6.

### Task 8 — Reference protection and cleanup integration

Affected:

- `backend/src/clothes_model/infrastructure/database/repositories.py`
- `modules/assets` reference queries; `modules/cleanup/service.py`
- focused tests

Work:

- Register outfit references (session/branch/revision/`pending_reapply`) in the asset reference graph.
- Block deleting referenced person/garment assets, listing affected references; extend cleanup so outfit
  dependencies are never auto-expired while referenced, and release normally after the last reference is
  removed.

Verify:

- Tests for deletion blocking + reference listing, cleanup exclusion while referenced, and release after
  removing references; no cascade deletion.

Dependencies: Tasks 3, 5.

### Task 9 — Jobs and capability integration hardening

Affected:

- job creation/validation; Provider capability checks
- focused tests

Work:

- Enforce `sequential_layering` and `supported_layer_roles` (and consider `preserve_existing_garments`)
  at layer job creation; keep V1 job behavior unchanged when no outfit context is present.

Verify:

- Tests that V1 jobs are unaffected and V1.1 jobs reject capability-incompatible Providers.

Dependencies: Task 4.

### Task 10 — Android V1.1 entry and session list

Affected:

- Android home mode card enablement; new V1.1 navigation route and session-list screen
- reusable asset components

Work:

- Enable the "分层穿搭" mode card; add the independent session list (create/continue, favorite, rename).
- Keep the bottom navigation unchanged.

Verify:

- Compose/JVM tests for entry, list states, and unchanged V1 navigation.

Dependencies: Tasks 1, 3.

### Task 11 — Android workbench and layer management

Affected:

- workbench screen, layer list, candidate confirmation, asset selector reuse
- state holders

Work:

- Workbench shows the current confirmed image, applied layers, and addable system layer types.
- Apply a layer (choose garment/Provider/candidates), then require explicit candidate selection to commit
  a revision; unselected candidates remain usable to start a new outfit.
- Replace/remove/revert layers with `pending_reapply` presentation and explicit reapply/replace/remove.

Verify:

- Compose tests for apply, confirmation, modify → `pending_reapply`, and revert.

Dependencies: Tasks 4, 5, 10.

### Task 12 — Android branches, route switch, reapply, and protected deletion

Affected:

- branch history screen, reapply flow, route switch, reference-blocked deletion UI

Work:

- Branch history with naming/favorite/mainline; route switch with preserved-outerwear explanation.
- Reapply flow with explicit compatible-Provider selection and configuration-change presentation.
- Show reference-blocked deletion with the list of references to resolve.

Verify:

- Compose tests for branch creation/switch, route switch, reapply, and blocked deletion.

Dependencies: Tasks 6, 7, 11.

### Task 13 — Integrated V1.1 verification and gate

Affected:

- `verify-phase9.ps1` (new); `.github/workflows/ci.yml` (Phase 9 gate job)
- README, roadmap, this plan

Work:

- Add a Phase 9 gate: contract, Backend (unit/migration/HTTP), Android build/lint/unit/instrumentation
  compile, and V1 regression (no V1 behavior change).
- Record V1.1 acceptance scenarios 23–37 status.

Verify:

- `verify-phase9.ps1` passes; V1 regression and Phase 8 gate still pass.

Dependencies: Tasks 1–12.

### Task 14 — Documentation and release record

Affected:

- `docs/product-flow.md` cross-checks (already confirmed), roadmap, README, plan progress

Work:

- Record V1.1 completion, migration id, and deferred accepted items (e.g. real layered Provider
  acceptance if not available).

Verify:

- Roadmap/README reflect V1.1 status; no unclassified V1.1 scenario.

Dependencies: Task 13.

## Phase Exit Checklist

- [ ] Independent Android V1.1 entry with unchanged V1 bottom navigation and no V1 semantic changes.
- [ ] Session from one person image; four versioned system layer types; definition set locked per session.
- [ ] Immutable revisions committed only on explicit candidate selection; failed/cancelled/`needs_attention`
      never change the confirmed revision.
- [ ] Revert/replace/remove produce `pending_reapply` with no automatic jobs or fees.
- [ ] Split ↔ dress route switching creates a branch from the original person image and preserves
      compatible outerwear as `pending_reapply`; original branch unchanged.
- [ ] Reapply prefers original config but requires explicit compatible-Provider selection; no compatible
      Provider → `pending_reapply`, no job.
- [ ] Capability/role gating blocks incompatible layer jobs before creation; V1 jobs unaffected.
- [ ] Outfit references protect assets and are excluded from cleanup until released; deleting outfits never
      cascades to shared assets or other branches.
- [ ] V1.1 acceptance scenarios 23–37 have evidence; V1 regression and the Phase 8 gate still pass.
- [ ] Migration upgrades/downgrades cleanly on an existing V1 database.

## Risks

- The reference graph grows in complexity; incorrect `active`/reference handling could over- or
  under-protect assets. Cover with explicit tests.
- `pending_reapply` and route switching can be misread as automatic execution; the UI and API must never
  create a task without an explicit user action.
- Real layered generation requires a Provider declaring `sequential_layering` and the needed roles; the
  acceptance environment must have one before V1.1 generation is claimed ready.
- The V1 boundary scripts must stay meaningful after scoping; do not weaken V1 invariants.
- Keep V1 `TryOnJob` behavior byte-for-byte compatible when `outfit_context` is absent.

## Upstream Conflicts

None product-wise. The only intentional implementation change is narrowing the V1 contract boundary
scripts' "no outfit paths" assertion to the V1 surface so the additive V1.1 surface can exist; this does
not change confirmed V1 behavior.

## Implementation Handoff

Plan:
docs/plans/phase-9-layered-outfit-track.md

Current scope:
Phase 9 — V1.1 Layered Outfit Track

Start with:
Task 1 — Contract: Outfit surface, job outfit context, and boundary scoping

Recommended implementation scope:
Task 1 only, then Verify (contract-first; every consumer depends on the additive surface).

Prerequisite:
Accept the Phase 8 V1 release candidate (including the deferred credentialed AutoDL/Comfy acceptance)
before starting V1.1 implementation.

Implementation session should:
- read this persisted Plan and the Product Spec §2.3/§4.7/§9/§10/§18;
- inspect current tests, contract boundaries, reference graph, and Android reusable components;
- execute the selected Task's Work, run its Verify, and record material deviations;
- keep V1 精准换装 behavior and historical data unchanged.
