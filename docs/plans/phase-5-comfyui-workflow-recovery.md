# Phase 5 Implementation Plan

## Progress

- Status: COMPLETE FOR IMPLEMENTATION — deterministic exit gate passed; this implemented subsystem is
  now assigned to V1.1, with live acceptance deferred to the V1.1 release gate
- Planning mode: `PHASE_PLAN + LARGE`
- Planned: 2026-09-28
- Task 1: COMPLETE (contract, ADR, generated clients, and boundary verification)
- Task 2: COMPLETE (persistence, repositories, logical Provider bootstrap, and migration)
- Task 3: COMPLETE (secure node configuration, probing, audit, and idempotency)
- Task 4: COMPLETE (canonical immutable artifacts, manifest parser, and Admin reads)
- Task 5: COMPLETE (live validation, activation, retirement, rollback, and restart persistence)
- Task 6: COMPLETE (production Comfy adapter, deterministic fixture, and error/cleanup semantics)
- Task 7: COMPLETE (active Workflow locking, capability/category/mask rejection, and offline waiting)
- Task 8: COMPLETE (storage admission/pause, restart requery, availability pre-check, no-resubmit resume)
- Task 9: COMPLETE (redacted readiness diagnostics, CI Phase 5 gates, deployment script, proxy docs)
- Task 10: COMPLETE FOR CURRENT SCOPE — deterministic gate passed; live acceptance deferred
- Prerequisite: Phase 4 complete with credentialed real-Provider acceptance
- Last verified: 2026-09-28 with contract/generated gates plus 100 Backend tests, Ruff, and Pyright;
  `infra/verify-phase5-deployment.ps1` deterministic gate passed (31 focused tests); migration
  upgrade/downgrade and Phase 5 persistence suites passed.
- Task 8 deviation: in-process remote temp tracking is not persisted across restart; restart reconciles
  known `prompt_id` results but cannot re-issue remote temporary-file cleanup. Track in the deferred
  next-release acceptance/follow-up.
- Task 9/10 note: the Phase 5 contract boundary script and Compose deployment smoke run in CI; this
  environment ran the deterministic backend and migration gates only.
- Scope decision (2026-09-28): the product owner has not prepared the real Comfy Workflow/node and
  explicitly deferred credentialed AutoDL/Comfy acceptance to the next release. The implementation
  phase may close on deterministic evidence; Comfy production readiness may not be claimed yet.
- Deferred release gate: configure the authenticated node, validate/activate the real immutable
  Workflow, execute/persist one real output, prove restart and compatible-node recovery, and retain
  sanitized cleanup evidence before enabling Comfy for production use.
- Next action: implement Phase 6 Task 1 from
  [the persisted Phase 6 plan](phase-6-android-v1-completion.md); restore the deferred live gate when
  the real Workflow/node is available.

## Goal

Complete the V1 ComfyUI execution plane without changing the confirmed product model:

- one replaceable physical ComfyUI/AutoDL node;
- immutable API-format Workflow versions with validated bindings and capabilities;
- jobs that lock semantic Provider and Workflow versions but may resume on a compatible replacement node;
- durable upload, queue, query, output retrieval, cancellation, cleanup, restart, and storage-pressure behavior;
- conservative `needs_attention` handling whenever external state cannot be proved;
- contract, migration, integration, deployment, and operator evidence sufficient for Phase 6/7 clients to build on.

This phase implements Backend behavior, shared contracts, generated clients, operator APIs, and verification. It does not implement the complete Web Admin pages, Android mask editor, or the remaining Android/Web product surfaces assigned to Phases 6 and 7.

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 5.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md), especially ComfyUI Provider, Workflow versioning, recovery, storage, and security rules.
- [Product Flow](../product-flow.md), especially locked configuration, compatible-node recovery, `waiting_provider`, `needs_attention`, and storage blocking.
- [Web Admin UI Spec](../superpowers/specs/2026-09-24-web-admin-ui-design.md) for API-visible node, Workflow, diagnostics, and recovery semantics; full UI implementation remains Phase 7.
- [ADR-0004](../adr/0004-openapi-contract-ownership.md), [ADR-0005](../adr/0005-v1-single-instance-runtime.md), [ADR-0007](../adr/0007-private-content-addressed-storage.md), [ADR-0008](../adr/0008-durable-job-execution.md), and [ADR-0009](../adr/0009-synchronous-provider-completion.md).
- [Phase 3 Plan](phase-3-durable-jobs-provider-core.md) and [Phase 4 Plan](phase-4-minimum-v1-e2e.md), including their completed verification evidence.
- Current ComfyUI upstream routes and behavior must be pinned during implementation from the official repository rather than assumed from a third-party client. The currently relevant surface includes image upload, prompt submission, queue/history lookup, output retrieval, queue deletion/interruption, and server/node introspection.

## Current Repository State

- `backend/modules/workflows/http.py` contains contract-shaped stub routes only.
- `backend/modules/admin/http.py` contains stubbed singleton Comfy node configuration/test routes.
- OpenAPI already defines draft Workflow create/list/get/validate/activate shapes and the singleton Comfy node shape, but lacks enough immutable-artifact, compatibility, retirement/rollback, and execution-detail semantics for implementation.
- `ProviderAdapter` already supports availability, capabilities, submit, query, cancel, and output fetch. Both asynchronous fake execution and synchronous Ark completion use this boundary.
- `ProviderConfig`, immutable revisions, default selection, encrypted credentials, job snapshots, job items, external execution IDs, retry lineage, events, and generated outputs already exist.
- Jobs already have nullable `workflow_version_id` and `workflow_snapshot_json`, but no Workflow table or foreign key exists and job creation never selects or locks a Workflow.
- The scheduler durably claims `queued` and `waiting_provider` items. Expired `preparing` work safely returns to `queued`; expired `running` work conservatively enters `needs_attention`.
- Storage capacity blocks new jobs, but already-persisted queued work is not yet paused before claim/execution when reserve space is exhausted.
- `LocalFileStorage` provides confined atomic image storage and temporary cleanup, but has no immutable Workflow-artifact or Comfy temporary-file namespace.
- No production Comfy adapter, node repository, Workflow repository, Phase 5 migration, compatibility evaluator, deterministic Comfy server fixture, or Phase 5 deployment gate exists.

## Implementation Delta

### REUSE

- Provider registry/port, error taxonomy, invocation identity, job/item state machine, scheduler ownership, retry/requery commands, output publication, and late-result rejection.
- SQLite/Alembic/UoW repository patterns, encrypted secret envelope, Admin session/CSRF boundaries, idempotency records, security audit events, generated clients, and contract drift gates.
- Private storage confinement, atomic publication, authenticated output retrieval, asset references, structured logging, and deployment smoke patterns.

### NEW

- A singleton persisted physical Comfy node configuration with encrypted credentials and observed health/compatibility state.
- A system-owned logical Comfy Provider identity/revision that can be selected/defaulted without embedding the replaceable physical node address into locked job semantics.
- Immutable Workflow metadata, canonical API JSON/manifest artifacts, hashes, validation runs, activation history, and one-active-version-per-mode constraint.
- Manifest parser and binder for person, garment, optional mask, seed, candidate strategy, and declared outputs.
- Production Comfy transport for upload, prompt submission, query, output fetch, pending cancellation/current interruption, and bounded cleanup.
- Node compatibility checks using live server/node metadata plus the job's locked Workflow.
- Recovery reconciliation for node replacement, external query, output publication, temporary-file cleanup, and capacity pause/resume.
- Deterministic Comfy fixture and Phase 5 verification/deployment gates.

### MODIFY

- OpenAPI and all generated consumers.
- Provider invocation resolution and capabilities for the logical Comfy Provider.
- Job creation to lock an active compatible Workflow and reject permanent incompatibility before persistence.
- Scheduler/execution/command paths for storage admission, compatible-node waiting, Comfy cancellation, requery, and cleanup.
- Database models, repositories, UoW, migrations, application assembly, readiness/diagnostics, README, infra docs, and CI.

## Technical Decisions

### Logical Provider versus physical node

- Keep `ProviderConfig`/revision as the shared selectable Backend abstraction.
- Represent ComfyUI as one stable system-managed logical Provider. Its revision snapshots adapter semantics and Workflow-derived capabilities; it does not own the replaceable physical endpoint or credential.
- Store the actual endpoint, credential envelope, timeout, enablement, and last observed health in a dedicated singleton `ComfyNodeConfig` record.
- A job locks the logical Provider revision and exact Workflow version. At execution time the adapter resolves the current physical node and proves it is compatible with the locked Workflow before using it.
- Replacing the physical node therefore cannot rewrite a historical job, while a compatible replacement can resume `waiting_provider` work.

Record this boundary in a new ADR before schema/runtime implementation because it is long-lived and prevents accidental endpoint locking.

### Workflow artifacts and lifecycle

- Canonicalize and hash API-format Workflow JSON and the manifest independently.
- Store immutable canonical artifacts beneath a confined `workflows/` storage namespace using temporary write, fsync, and atomic replace. Database rows store metadata, hashes, relative artifact paths, validation results, state, and timestamps.
- Enforce uniqueness of `(workflow_id, version)` and immutability of artifact/hash fields after creation.
- Lifecycle remains exactly `draft -> validated -> active -> retired`. Validation failure leaves the version in `draft` with recorded diagnostics. Activating a validated/retired compatible version atomically retires the prior active version for the same mode; this is also rollback.
- Activation changes only future jobs. Jobs keep their exact Workflow ID, version, digest, bindings, and capability snapshot.

### Validation and compatibility

- Structural validation is deterministic and offline: schema version, node existence in Workflow JSON, binding paths, required inputs, output declarations, capability/binding consistency, candidate strategy, and safe value substitution.
- Live validation queries the configured node's node/object metadata, checks required node classes and accepted inputs, uploads sanitized test assets, runs one bounded test prompt, retrieves/validates one image, and attempts cleanup.
- Capabilities are declared by the manifest but become `verified` only after successful structural and live validation against the current node.
- A replacement node is compatible only when all node classes, bound inputs, output expectations, and required capabilities of the locked Workflow pass. Endpoint reachability alone is insufficient.

### External execution safety

- Persist the Comfy `prompt_id` as the external execution ID immediately after accepted submission.
- Use polling/history as the durable source of external truth; WebSocket events may optimize latency later but are not required for correctness.
- Pending queue deletion and current-process interruption are best-effort and have different scope. Never claim that a running prompt was cancelled unless external state proves termination; otherwise retain conservative state and cleanup rules.
- A timeout or disconnect after prompt submission is externally ambiguous unless the prompt can be correlated and queried. Do not resubmit automatically.
- Every remote filename/subfolder is generated from internal IDs, normalized, and treated as untrusted on response. Output retrieval is allow-listed by the locked manifest; response paths never become local filesystem paths.

### Storage pressure

- Keep the existing rule that new uploads/jobs fail when reserve capacity is unavailable.
- Add an execution admission check before claim and again before remote output retrieval/publication. Already-persisted work stays queued with `storage_capacity`; it is not failed and is resumed automatically when capacity returns.
- Remote completion discovered while local storage is blocked must retain the external ID and pollable state without discarding or repeatedly downloading the output.

## Target Architecture

```text
Admin API
  ├─ ComfyNodeService ── encrypted singleton node configuration
  └─ WorkflowService ─── immutable artifacts + validation + activation

Job create
  └─ logical Comfy Provider revision + active Workflow version snapshot

Scheduler / JobExecutionService
  └─ ComfyProviderAdapter
       ├─ resolve current physical node
       ├─ verify locked Workflow compatibility
       ├─ upload bounded private inputs
       ├─ bind and submit API-format prompt
       ├─ query by persisted prompt_id
       ├─ fetch allow-listed outputs into private FileStorage
       └─ clean remote temporary inputs/outputs best-effort
```

The single-instance scheduler remains the only execution owner. No distributed queue, extra database, independent Worker, or multi-node load balancer is introduced.

## Contract and Integration Strategy

- Extend existing schemas additively; regenerate Backend, Android, and Web clients from the canonical OpenAPI source.
- Make Workflow responses expose stable identity/version/state, immutable digests, redacted manifest summary, capabilities, validation checks, and activation timestamps without returning secret node data.
- Add explicit retire/rollback semantics only where the existing activate operation cannot express confirmed behavior clearly. A rollback is activation of a previously validated/retired immutable version, not mutation of history.
- Expose node health separately from Workflow compatibility. A node can be reachable but incompatible.
- Ensure job payloads carry the locked Workflow ref/snapshot for Comfy jobs and omit it for LLM jobs.
- Preserve existing LLM Provider and Phase 4 request/response behavior.

## Tasks

### Task 1 — Close Phase 5 contracts and record the execution boundary — COMPLETE

Affected:

- `contracts/openapi/paths/workflows.yaml`
- `contracts/openapi/components/workflows/schemas.yaml`
- `contracts/openapi/paths/admin.yaml`
- `contracts/openapi/components/admin/schemas.yaml`
- job/provider/common schemas only where locked Workflow or logical Comfy Provider semantics require it
- `contracts/tooling/verify-phase5-boundaries.ps1`
- generated Backend/Android/Web consumers
- new ADR under `docs/adr/`

Work:

- Define immutable Workflow artifact metadata, validation checks, compatibility result, activation/rollback behavior, and redacted node status.
- Define the stable logical Comfy Provider identity and explicitly separate it from the replaceable physical node.
- Specify job locking, waiting, cancellation/requery, storage blocking, and error codes without adding client-local states.
- Document the current upstream protocol surface and cancellation limitations in the ADR; pin implementation assumptions to tested behavior rather than a floating third-party SDK.
- Regenerate all consumers and add Phase 5 boundary assertions.

Verify:

- OpenAPI lint, bundle, additive compatibility, Phase 1–4 boundary checks, new Phase 5 checks, generated drift, Backend model type check, Web generated compile, and Kotlin generated compile pass.
- Contract examples cover offline node, incompatible node, failed validation, active/retired Workflow, locked job snapshot, storage wait, and ambiguous external execution.
- No existing Ark/LLM operation, security scheme, enum meaning, or Phase 4 payload is removed or silently redefined.

Dependencies and parallelization:

- No implementation dependency beyond completed Phase 4.
- Must complete before database/API/runtime tasks. Review the ADR and generated diff before Task 2.

### Task 2 — Add Comfy node and Workflow persistence with reversible migration — COMPLETE

Affected:

- `backend/infrastructure/database/models.py`
- `backend/infrastructure/database/repositories.py`
- UoW exports/protocols
- new Workflow and Comfy node domain/application modules
- new Alembic revision after `20260927_0003`
- migration and persistence tests

Work:

- Add singleton Comfy node configuration, encrypted credential envelope metadata, health observation, and update timestamps.
- Add logical Comfy Provider bootstrap identity/revision without storing a physical endpoint in locked semantics.
- Add Workflow version, artifact digest/path, manifest/capability snapshot, validation record, activation, and retirement persistence.
- Enforce `(workflow_id, version)` uniqueness, one active Workflow per mode, immutable artifact identity, and valid lifecycle transitions.
- Add a real Workflow foreign key/reference relationship for new jobs while preserving existing Phase 1–4 jobs with null Workflow fields.

Verify:

- Empty, Phase 2, Phase 3, and current Phase 4 databases upgrade to Phase 5 head.
- Downgrade/re-upgrade preserves all pre-Phase-5 data and removes only Phase 5 structures.
- Singleton, uniqueness, immutable-version, lifecycle, one-active-per-mode, locked-reference, and concurrent activation tests pass on pinned SQLite.
- Existing jobs, outputs, Provider revisions, and Ark default selection remain readable and unchanged.

Dependencies and parallelization:

- Depends on Task 1.
- Repository/domain work may be split internally, but merge only with the migration and persistence tests together.

### Task 3 — Implement secure singleton Comfy node configuration and health probing — COMPLETE

Affected:

- `backend/modules/admin/http.py`
- new Comfy node application/domain/infrastructure files
- application assembly and secret-purpose constants
- Admin HTTP/security tests

Work:

- Replace Comfy node stubs with get/update/test behavior using Admin session, CSRF, idempotency where declared, and encrypted write-only credentials.
- Retain the existing credential when an update omits it; never return or log it.
- Validate endpoint scheme/host policy, bounded timeout, response size, redirects, and credential forwarding so the Backend cannot be used as an unrestricted network proxy.
- Probe server identity/system/node metadata and record `healthy`, `offline`, `incompatible`, or `unchecked` independently from Workflow validation.
- Updating/disabling/replacing the node must not rewrite locked jobs or Workflow versions.

Verify:

- Tests cover create/update, omitted-secret retention, rotation, redaction, missing master key, CSRF/session scope, idempotency, redirect/host rejection, timeout, malformed responses, and audit metadata.
- App Token cannot read or mutate node configuration.
- Logs, errors, database snapshots, and API responses contain no complete credential or upstream response body.

Dependencies and parallelization:

- Depends on Tasks 1–2.
- Can proceed in parallel with Task 4 after shared persistence interfaces stabilize.

### Task 4 — Store immutable Workflow artifacts and validate manifest structure — COMPLETE

Affected:

- `backend/modules/workflows/`
- confined Workflow artifact storage under Backend infrastructure storage
- Workflow repositories/services and HTTP routes
- contract-facing Workflow tests

Work:

- Replace create/list/get stubs with immutable version creation, canonical JSON/manifest hashing, atomic artifact publication, and idempotent request handling.
- Implement a versioned manifest parser for person, garment, optional mask, seed, candidate strategy, outputs, and capability declarations.
- Validate Workflow graph node IDs, bound input names/value shapes, declared outputs, required bindings, and capability consistency without contacting the node.
- Reject duplicate version numbers with different content; return the existing resource for an identical idempotent creation.
- Never expose arbitrary artifact paths; provide only redacted structured metadata needed by Admin clients.

Verify:

- Unit/property tests cover canonicalization, digest stability, duplicate keys/version conflicts, malformed/deep/oversized JSON, invalid bindings, path confinement, atomic-write failure, and restart reads.
- Structural validation detects missing nodes/inputs/outputs and contradictory capabilities deterministically.
- A database failure after file publication or file failure before commit leaves no visible partial Workflow and is reconciled safely.

Dependencies and parallelization:

- Depends on Task 2.
- Can run in parallel with Task 3; Task 5 depends on both.

### Task 5 — Implement live validation, activation, retirement, and rollback

Affected:

- Workflow application services/HTTP routes
- Comfy node client/introspection boundary
- test asset fixtures and validation tests
- logical Comfy Provider capability revision updates

Work:

- Compare locked manifest requirements with live node/object metadata and produce stable per-check diagnostics.
- Run one explicit bounded minimal test: upload sanitized fixtures, bind the prompt, submit, query, fetch one output, validate image bounds, and clean remote temporary files.
- Mark a version `validated` only after structural and live validation pass; record the node observation used without making the Workflow artifact mutable.
- Atomically activate a compatible version for its mode, retire the previous active version, and update the logical Comfy Provider capability revision for future jobs.
- Implement rollback by reactivating a previously validated/retired immutable version after compatibility confirmation.

Verify:

- Tests cover reachable-but-incompatible nodes, missing custom nodes/models, invalid input types, test-run rejection/failure/timeout, malformed output, cleanup failure, concurrent activation, rollback, and restart.
- Activation/default changes do not rewrite existing jobs or their snapshots.
- Validation diagnostics are useful but contain no original test image, credential, complete Workflow body, or unsafe upstream detail.

Dependencies and parallelization:

- Depends on Tasks 3–4.
- Must establish the validated active Workflow before real job execution in Tasks 6–7.

### Task 6 — Implement the production Comfy Provider transport

Affected:

- `backend/modules/providers/infrastructure/` new Comfy adapter/client
- Provider registry and application assembly
- Provider contract tests and deterministic Comfy fixture

Work:

- Resolve the current physical node separately from the locked Provider/Workflow snapshot.
- Upload person, garment, and optional mask inputs with collision-resistant job/item-scoped names.
- Fill a deep copy of the locked API Workflow from validated bindings; never mutate the stored artifact.
- Submit the prompt, persist/return the external prompt ID, query durable history/queue state, fetch only declared outputs, normalize error classes, and support bounded cancellation.
- Track every remote temporary input/output known to the attempt and issue best-effort cleanup on success, failure, cancellation, rejection, and late result.
- Treat every upstream filename, content type, JSON field, status, and body size as untrusted.

Verify:

- The reusable Provider contract suite passes for Comfy alongside fake and Ark adapters.
- Deterministic fixture tests cover upload, binding, submission, queued/running/succeeded/failed state mapping, multi-output selection, fetch, pending deletion, running interruption limitation, malformed/oversized data, authentication, timeout, and cleanup.
- Ambiguous post-submit failure never causes an automatic second prompt.
- Production registry permits the Comfy adapter and still rejects fake adapters.

Dependencies and parallelization:

- Depends on Tasks 3–5.
- Transport mechanics may be developed against the deterministic fixture while Task 5 finalizes activation, but integration waits for the locked Workflow resolver.

### Task 7 — Lock Workflow versions at job creation and enforce compatibility

Affected:

- `backend/modules/jobs/http.py`
- job/domain payloads and repositories
- Provider/default selection services
- job creation and HTTP tests

Work:

- When a Comfy Provider is selected, resolve the active Workflow for the requested mode, verify capability/category/mask/candidate requirements, and snapshot its identity, digest, bindings, and capabilities transactionally with the job.
- Reject creation when no active Workflow exists or configuration is permanently incompatible.
- Persist `waiting_provider` when the physical node is disabled/offline; preserve the locked Workflow indefinitely.
- Keep Ark/LLM jobs Workflow-free and behavior-compatible.
- On explicit retry with a replacement Provider, capability-check and snapshot the newly selected semantic configuration without rewriting the original attempt.

Verify:

- Job tests cover active Workflow locking, later activation/rollback isolation, node replacement, category/mask/candidate incompatibility, offline waiting, idempotent duplicate creation, and explicit retry Provider replacement.
- Existing Phase 4 Android one-candidate requests continue to succeed unchanged against Ark.
- Job payloads expose the exact locked Workflow reference/snapshot and never the mutable current active version.

Dependencies and parallelization:

- Depends on Tasks 2 and 5; execution paths also depend on Task 6.

### Task 8 — Complete scheduler recovery, storage pause, cancellation, and cleanup semantics

Affected:

- scheduler claim/reconciliation
- `JobExecutionService` and command services
- Comfy compatibility/resolution and cleanup reconciliation
- storage admission service
- scheduler, command, restart, and fault-injection tests

Work:

- Check storage reserve before claim and output publication; retain queued work with `storage_capacity` and resume automatically after safe capacity returns.
- Re-evaluate the current node against each locked Workflow before moving `waiting_provider` to `preparing`.
- Requery persisted Comfy prompt IDs after restart; synchronize known queued/running/succeeded/failed states and enter `needs_attention` only when state is genuinely unprovable.
- Distinguish pending queue deletion from running interruption and preserve conservative local state on uncertain cancellation.
- Reconcile orphaned local staging and known remote temporary artifacts without deleting user assets, Workflow artifacts, or outputs referenced by history.
- Preserve late-result rejection and compensate any fetched-but-unpublished files.

Verify:

- Fault injection covers crashes before/after upload, submit acceptance, prompt-ID persistence, output discovery, download, normalization, DB commit, and remote cleanup.
- Offline nodes wait indefinitely; compatible replacements resume; incompatible replacements remain waiting with actionable reason; cancelled work never resumes.
- Storage-blocked queued work is not claimed or failed and resumes after capacity recovers.
- Restart/requery never duplicates external execution or visible output.

Dependencies and parallelization:

- Depends on Tasks 6–7.
- Can be split between scheduler admission and external reconciliation only if shared state transitions remain covered by one integration suite.

### Task 9 — Add Phase 5 observability, CI, and deployment verification

Affected:

- readiness/diagnostic payloads and safe structured logging
- `.env.example`, `infra/compose.yaml`, `infra/README.md`
- new `infra/verify-phase5-deployment.ps1`
- `.github/workflows/ci.yml`
- test fixture/server tooling
- root/backend README documentation

Work:

- Expose redacted node health, active Workflow identity, waiting/storage-blocked counts, and cleanup conclusions without endpoint credentials, Workflow bodies, filenames, prompts, or images.
- Add a deterministic local Comfy fixture to normal CI for upload/submit/query/fetch/cancel/restart paths.
- Add an opt-in real AutoDL/Comfy smoke path that uses secure environment secrets and explicitly bounded executions; never run it on ordinary pull requests.
- Extend deployment verification through node configuration, Workflow create/validate/activate, Comfy job execution, output persistence, restart/requery, node replacement, storage blocking, and cleanup evidence.
- Document the protected-network requirement for raw ComfyUI and the supported authenticated proxy/private-tunnel boundary.

Verify:

- Contract, Backend lint/type/full tests, generated clients, deployment smoke, migration, Phase 1–4 regression, single-instance, and redaction gates pass.
- Static/runtime scans find no Comfy credential, Authorization value, complete Workflow JSON, prompt body, source image, output image, or unsafe remote path in repository, logs, reports, or Web bundles.
- The deterministic gate requires no GPU/network/paid service; credentialed smoke is opt-in and bounded.

Dependencies and parallelization:

- Depends on Tasks 1–8 for final scripts; documentation/fixture scaffolding may begin after Task 1.

### Task 10 — Run the integrated Phase 5 exit gate — COMPLETE FOR CURRENT SCOPE

Affected:

- all Phase 5 suites and smoke scripts
- `README.md`
- `docs/roadmap/implementation-roadmap.md`
- this plan's progress/checklist

Work:

- Run all contract, generation, Backend, migration, Provider, scheduler, deployment, restart, storage-pressure, security, and cleanup gates from a clean checkout/deployment.
- Deferred to the next release by the 2026-09-28 scope decision: run one operator acceptance against
  the intended authenticated AutoDL/Comfy node with an immutable validated Workflow.
- Replace the physical node configuration with a compatible endpoint or deterministic equivalent and prove the same locked waiting job can continue without snapshot mutation.
- Capture only sanitized IDs, state transitions, hashes/sizes, timings, compatibility conclusions, and cleanup counts.
- Close the current implementation phase after deterministic evidence; do not mark Comfy production
  readiness until real private output persistence, restart-safe reconciliation, compatible-node
  recovery, and cleanup behavior are evidenced.

Verify:

- Every current-scope Phase Exit Checklist item has automated evidence; explicitly deferred live
  infrastructure items remain unchecked release-readiness requirements.
- Phase 1–4 gates remain green.
- README, Roadmap, and this plan agree on completion state and the next phase.

Dependencies and parallelization:

- Depends on Tasks 1–9.
- This is the final Phase 5 task and must not pull full Android or Web Admin UI work forward.

## Phase Exit Checklist

### Deterministic exit evidence recorded 2026-09-28

- Backend Ruff, strict Pyright, and the full Pytest suite passed (100 tests) without network, GPU, or paid access.
- `infra/verify-phase5-deployment.ps1` deterministic gate passed (31 focused Comfy/Workflow/recovery tests).
- Migration upgrade/downgrade/re-upgrade and Phase 5 persistence suites passed.
- Phase 5 contract generation, generated-client drift, Backend model typing, and Phase 5 boundary assertions are enforced by CI.
- Deterministic scenarios covered: node configuration/redaction, immutable artifacts, structural + live validation, activation/retirement/rollback, Workflow locking at creation, category/mask/candidate rejection, offline waiting, storage pause/resume, blocked-completion no-resubmit, and restart requery.
- Deferred release evidence: one bounded operator acceptance against a real authenticated
  AutoDL/Comfy node and compatible-node replacement on real infrastructure.

### Contract and architecture

- [x] Logical Comfy Provider, physical node, and locked Workflow responsibilities are explicit and ADR-backed.
- [x] Phase 5 contract additions are additive, generated without drift, and compile for Backend/Android/Web.
- [x] Existing Ark/LLM and Phase 4 client behavior remains compatible.
- [x] No Phase 6/7 full UI or Phase 9 Outfits implementation is pulled forward.

### Persistence and Workflow lifecycle

- [x] All supported prior databases upgrade and downgrade/re-upgrade deterministically.
- [x] Workflow JSON/manifest artifacts are canonical, hashed, confined, immutable, and restart-safe.
- [ ] Structural/live validation and `draft -> validated -> active -> retired` transitions are persisted.
      (Deviation: validation is persisted as `validated_at` plus recorded checks; the lifecycle state
      column remains the 3-state `draft/active/retired` set. Behavior matches; the literal `validated`
      state name is not stored. Reconcile contract enum vs domain in a follow-up.)
- [x] Only one Workflow per mode is active; rollback changes future jobs only.

### Node and Provider security

- [x] The singleton node credential is encrypted, write-only, redacted, and retained when omitted on update.
- [x] Endpoint/redirect/size/timeout controls prevent unrestricted proxying and credential exfiltration.
- [x] Raw ComfyUI is documented and verified behind an authenticated proxy or private channel.
- [x] A reachable but incompatible node cannot execute a locked Workflow.

### Execution and recovery

- [x] Comfy upload, bind, submit, query, fetch, cancel attempt, and output publication pass the Provider contract suite.
- [x] Jobs lock Provider and Workflow versions while compatible replacement nodes can resume waiting work.
- [x] Offline nodes wait indefinitely; cancelled work never resumes.
- [x] Restart/requery and ambiguous outcomes never duplicate prompts, fees, or visible outputs.
- [x] Pending cancellation, running interruption, and `needs_attention` retain distinct truthful semantics.

### Storage and cleanup

- [x] Storage pressure rejects new work and pauses persisted queued work without failing it.
- [x] Space recovery resumes eligible work automatically.
- [ ] Remote and local temporary files are cleaned after success, failure, cancellation, and late-result paths.
      (Partial: in-process remote cleanup is verified; restart cannot re-issue cleanup for a lost
      `prompt_id`→remote-file map. Local staging uses the existing reconcile path.)
- [x] Cleanup never removes locked Workflow artifacts, source assets, or published outputs required by history.

### Integration and operations

- [x] Deterministic no-GPU/no-network Phase 5 verification runs in normal CI.
- [ ] Clean deployment can configure a node, create/validate/activate a Workflow, execute a job, persist output, restart, and recover.
      (Deterministic equivalent verified in tests; the real Compose + AutoDL loop requires operator infrastructure.)
- [ ] Compatible-node replacement is verified without mutating the locked job snapshot.
      (Locking and compatibility rejection verified deterministically; live node-swap requires operator infrastructure.)
- [x] Logs, events, diagnostics, reports, and artifacts are free of secrets, Workflow bodies, prompts, and image payloads.
- [ ] DEFERRED TO NEXT RELEASE — bounded credentialed operator acceptance against the target
      AutoDL/Comfy environment is recorded before claiming Comfy production readiness.

## Migration and Rollback

- Use one additive Phase 5 migration for node/Workflow persistence and the logical Comfy Provider bootstrap. Rebuilding the jobs table is permitted only if SQLite requires it for the Workflow foreign key and migration tests prove complete Phase 4 preservation.
- Existing jobs retain null Workflow references and remain valid.
- Workflow artifacts are written before metadata publication with compensation on transaction failure; rollback of the application must not delete artifacts or historical rows.
- Operational rollback disables the logical Comfy Provider/node and restores Ark as default. Existing Comfy jobs remain readable and wait or require attention; they are never silently routed to Ark.
- Database downgrade is for controlled deployment rollback only and must refuse or explicitly preserve/export Phase 5 data that cannot be represented safely. The implementation must not pretend a destructive downgrade is lossless.
- Credential revocation occurs at the proxy/node and the local encrypted value is then replaced or disabled; credentials are never recovered from logs or API responses.

## Risks

- ComfyUI's server API is implementation-facing and can evolve. Pin the tested server revision/image and keep protocol parsing isolated behind the adapter.
- Generic interruption may affect the currently running prompt rather than a specific prompt. Prefer precise pending deletion; expose running interruption as best-effort and conservative.
- Custom nodes can change names, inputs, and output shapes without the Workflow JSON changing. Live object-metadata validation and a bounded test run are required before activation and after node replacement.
- Remote cleanup can fail after a successful local publish. Track known remote artifacts, retry bounded cleanup, and report sanitized residue without deleting unrelated node files.
- Large Workflow JSON, images, history payloads, and outputs can exhaust memory or disk. Bound all request/response sizes and stream file transfers where possible.
- SQLite/file publication cannot be globally atomic. Preserve the existing compensation/reconciliation pattern and test every crash boundary.
- A node may be reachable but missing models/custom nodes. Health and Workflow compatibility must remain separate conclusions.

## Upstream Conflicts

None identified.

The confirmed Product Spec already resolves the material behavior: one physical node, immutable Workflow versions, compatible-node migration, indefinite `waiting_provider`, no blind retry after ambiguous execution, and explicit activation/default boundaries. Planning therefore makes only repository-consistent technical choices and does not reopen product or UI decisions.

## Implementation Handoff

- Plan: `docs/plans/phase-5-comfyui-workflow-recovery.md`
- Scope: Phase 5 only — logical Comfy Provider, singleton physical node, immutable Workflow versions, Comfy execution, recovery, storage pause, cleanup, and verification.
- Continue with: Phase 6 Task 1 — close Android V1 contract and Backend behavior gaps.
- Phase 5 evidence: all 10 implementation tasks are committed; contract/generated gates, 100 Backend
  tests, Ruff, Pyright, the 31-test deterministic deployment gate, migrations, restart/recovery, and
  redaction checks pass.
- Deferred prerequisite: prepare a real authenticated AutoDL/Comfy environment and immutable Workflow
  before restoring the next-release production-readiness acceptance.
- External prerequisite: a real authenticated AutoDL/Comfy environment is not needed during Phase 6;
  it becomes mandatory when the deferred production-readiness gate resumes.
- Execution rule: preserve the deterministic P5 gates while Phase 6 proceeds; do not enable Comfy in
  production until the deferred credentialed acceptance is recorded.
