# ComfyUI V1.1 Release-Track Plan

## Progress

- Status: IN PROGRESS — Tasks 1–2 complete
- Planning mode: `PLAN_UPDATE + MEDIUM`
- Planned: 2026-10-08
- Confirmed change: ComfyUI node, Workflow, selection, waiting/recovery, diagnostics, and credentialed
  production acceptance belong to V1.1. V1 ships with the verified direct-model Provider.
- Product source: [merged change](../changes/defer-comfyui-node-to-v1-1.md), the updated Product Spec,
  Product Flow, and V1 acceptance matrix.
- Completed: Task 1 added the deployment release descriptor, health feature list, generated clients, and
  deployment defaults.
- Verified: contract lint/additive/boundary/Prism gates; generated drift, Python type checks, Web
  generated type checks, Android generated-client compilation; six focused Backend settings/health tests.
- Next action: implement Task 3 Web Admin and Android presentation gating.

## Goal

Make the confirmed version boundary executable rather than documentary only:

- a V1 deployment cannot advertise, select, configure, or submit ComfyUI work;
- a V1.1 deployment retains the already implemented ComfyUI and layered-outfit behavior;
- existing ComfyUI code, schema, history, and tests remain intact;
- deterministic V1 release evidence no longer depends on a real AutoDL node;
- V1.1 cannot claim ComfyUI production readiness until credentialed acceptance passes.

## Current State

- Backend always registers ComfyUI and Workflow routes, seeds the logical Comfy Provider, returns it from
  Provider/Admin APIs when active, and accepts ComfyUI jobs when configuration is usable.
- Web Admin always renders `ComfyUI 节点` and `Workflows` navigation/routes and ComfyUI status in the
  overview.
- Android consumes the available-Provider API and therefore can select any Provider returned by the
  Backend; no release-track concept exists.
- Contract and generated clients have no server feature/release descriptor.
- `verify-phase8.ps1` and the V1 acceptance matrix still carry historical ComfyUI evidence even though
  the confirmed Product Spec now assigns those scenarios to V1.1.
- Database tables and historical records already support ComfyUI. No destructive migration is needed.

## Implementation Delta

- **NEW**: deployment-level `product_release` (`v1` or `v1_1`) and a contract-visible feature descriptor.
- **MODIFY**: Backend availability and mutation guards so V1 excludes ComfyUI at the authoritative API
  boundary, including direct requests that bypass clients.
- **MODIFY**: Web Admin navigation, routes, overview, and diagnostics to follow server features.
- **REUSE**: Android Provider filtering through the Backend availability API; add only contract/model
  handling needed to prove the release boundary and avoid client-side invention.
- **MODIFY**: Phase 8 and Phase 9 verification profiles and release records.
- **PRESERVE**: ComfyUI modules, Workflow tables, migrations, historical references, Provider abstractions,
  durable job states, and all V1.1 behavior.

## Technical Decisions

- The Backend is the authority for enabled product features. UI-only flags are insufficient because a
  client could call hidden APIs directly.
- Add `CLOTHES_MODEL_PRODUCT_RELEASE=v1|v1_1`; default to `v1` so a fresh production deployment does not
  accidentally expose an unaccepted ComfyUI path. CI/dev profiles that exercise V1.1 set `v1_1`.
- Expose the release and enabled features in the existing health/system capability surface through the
  OpenAPI contract. Clients may hide presentation from this descriptor, but Backend guards remain final.
- Do not delete or conditionally migrate ComfyUI persistence. Release gating affects availability and
  mutation, not history.
- Changing a running deployment from `v1_1` back to `v1` while unfinished ComfyUI jobs exist is not a
  supported downgrade. Startup/readiness must report the conflict rather than silently abandoning work.

## Tasks

### Task 1 — Contract and deployment release descriptor

Status: COMPLETE (2026-10-08)

Affected:

- `contracts/openapi/components/common/schemas.yaml`
- health/system paths and generated clients
- `backend/src/clothes_model/core/config.py`
- `.env.example`, `infra/compose.yaml`, deployment documentation

Work:

- Add `product_release` and a stable enabled-feature list containing at least `comfyui` and
  `layered_outfits`.
- Add `CLOTHES_MODEL_PRODUCT_RELEASE` validation and safe-log context without exposing secrets.
- Define `v1` as direct-model precise try-on and `v1_1` as layered outfits plus ComfyUI.
- Regenerate Python, Web, and Android contract clients.

Verify:

- Contract lint/generation/parity gates pass.
- Settings tests cover valid values, invalid values, and the safe default.
- Generated clients expose identical release/feature semantics.

Dependencies: none.

### Task 2 — Enforce the Backend boundary

Status: COMPLETE (2026-10-08)

Affected:

- Provider listing/default/configuration endpoints
- job create/retry and outfit add/reapply services
- Comfy node and Workflow Admin endpoints
- system overview/readiness
- focused Backend tests

Work:

- In `v1`, omit ComfyUI from selectable and Admin Provider lists, prevent it from becoming default, and
  reject ComfyUI create/retry/outfit requests with a stable `feature_not_available` problem.
- In `v1`, reject Comfy node/Workflow mutation and operation endpoints while preserving stored data and
  historical job reads.
- Remove ComfyUI from V1 overview dependencies/action items and report the active release descriptor.
- In `v1_1`, preserve current behavior byte-for-byte except for the new descriptor.
- Detect unsupported `v1_1` → `v1` startup/readiness when unfinished ComfyUI jobs exist; do not mutate
  their state automatically.

Verify:

- Backend tests prove direct API bypass cannot create or re-enable ComfyUI work in V1.
- Regression tests prove V1.1 list/config/job/recovery behavior remains available.
- Historical ComfyUI jobs and references remain readable in both profiles.

Dependencies: Task 1.

### Task 3 — Gate Web Admin and Android presentation

Affected:

- `web-admin/src/app/AppShell.tsx`, router, overview, Provider/default-backend/diagnostics presentation
- associated React tests
- Android feature/release model and focused ViewModel tests

Work:

- Load the server feature descriptor after authentication.
- In V1, remove ComfyUI/Workflow navigation, redirect guarded routes, omit active-Workflow summaries, and
  exclude ComfyUI from default/configuration actions.
- In V1.1, retain the current screens and routes.
- Keep Android dependent on the Backend's filtered Provider list; consume the descriptor only where the
  UI must explain unavailable V1.1 capabilities. Do not duplicate Provider eligibility rules locally.

Verify:

- Web tests cover both release profiles, including direct navigation to a disabled route.
- Android unit/UI tests prove V1 never offers ComfyUI and V1.1 capability-driven selection still works.
- Accessibility/navigation tests remain green.

Dependencies: Tasks 1–2.

### Task 4 — Split V1 and V1.1 deterministic gates

Affected:

- `verify-phase8.ps1`, `verify-phase9.ps1`
- `.github/workflows/ci.yml`
- acceptance fixtures and release-boundary scans

Work:

- Run the Phase 8 release profile with `product_release=v1`; assert direct-model generation, manual-mask
  support, and absence/rejection of ComfyUI product surfaces.
- Run the Phase 9 profile with `product_release=v1_1`; retain ComfyUI/Workflow deterministic tests and
  layered-outfit regression coverage.
- Keep real credentialed AutoDL/Comfy acceptance as a manual V1.1 release gate, not a V1 gate.

Verify:

- Both deterministic gates pass independently from clean configuration.
- V1 gate fails if ComfyUI becomes selectable or mutable.
- V1.1 gate fails if the ComfyUI/Workflow or layered-outfit surfaces disappear.

Dependencies: Tasks 2–3.

### Task 5 — Rebaseline release records and runbooks

Affected:

- `README.md`
- `docs/roadmap/implementation-roadmap.md`
- Phase 5, Phase 8, and Phase 9 plan progress sections
- V1/V1.1 acceptance records and relevant runbook labels

Work:

- Record Phase 5 as early implementation of a V1.1 subsystem, not a V1 release dependency.
- Record Phase 8 as the direct-model V1 release gate.
- Record Phase 9 as implementation-complete but V1.1 production readiness pending real ComfyUI
  acceptance until that evidence exists.
- Preserve historical dates and test evidence; change version ownership rather than pretending work was
  not completed.

Verify:

- Repository-wide wording no longer claims credentialed ComfyUI acceptance blocks V1.
- Every ComfyUI production-readiness statement points to V1.1.
- Roadmap, README, Product Spec, Product Flow, acceptance matrix, and phase plans agree.

Dependencies: Task 4.

## Final Verification

- `verify-phase8.ps1` passes under `v1` without a ComfyUI node/Workflow.
- `verify-phase9.ps1` passes under `v1_1` with deterministic Comfy fixtures.
- Real credentialed AutoDL/Comfy acceptance remains visibly pending for V1.1.
- V1 Android/Web cannot select or configure ComfyUI, including direct URL/API attempts.
- Existing V1.1 data and history survive profile-aware builds without migration or deletion.

## Risks

- UI-only hiding would leave an unsafe direct API path; Backend rejection is mandatory.
- A release setting that silently changes on an existing deployment could strand active work; downgrade
  detection must be explicit.
- Generated-client churn can obscure behavioral changes; contract and boundary checks must run first.
- Overview/readiness must not mark V1 unhealthy merely because ComfyUI is absent.

## Implementation Handoff

Plan:
`docs/plans/release-track-comfyui-v1-1.md`

Current scope:
ComfyUI V1.1 release-track enforcement and release-gate rebaseline.

Start with:
Task 2 — Enforce the Backend boundary.

Recommended implementation scope:
Task 2, then focused Backend boundary verification before presentation gating.

Implementation session should:

- read the merged change, updated Product Spec/Product Flow, and this plan;
- preserve existing ComfyUI code and historical data;
- make the Backend the feature authority;
- run each Task's Verify section before continuing;
- record material deviations in this plan.
