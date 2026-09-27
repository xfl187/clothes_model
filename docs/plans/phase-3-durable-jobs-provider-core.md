# Phase 3 Implementation Plan

## Goal

建立 V1 的持久任务核心和统一 Provider 执行平面：任务创建后立即持久化，候选可以独立领取、等待、执行、取消和重试；服务重启后不会丢失任务，也不会因为不确定的外部执行状态而盲目重复调用 Provider。

本阶段实现 Backend 任务、Provider 配置与调度基础，并用确定性的契约级 fake Provider 完成真实持久化执行闭环。真实 LLM 厂商适配、Web Admin 配置页面、Android 正式任务 UI、ComfyUI 和 Workflow 生命周期分别留在 Phase 4–7。

## Progress

- Status: IN PROGRESS
- Task 1 — COMPLETE (2026-09-27; contract additions, ADR-0008, Phase 3 boundary gate)
- Task 2 — COMPLETE (2026-09-27; migration 0003, provider/job repositories, invariant tests)
- Tasks 3–11 — NOT_STARTED
- Current: Task 3 — Implement Provider configuration, snapshots, and adapter contract
- Last updated: 2026-09-27
- Next: implementation Task 3 only, then verify the Provider contract suite boundary

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 3 — Durable Job and Provider Core.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md), especially sections 5, 6, 9, 16–18.
- [Product Flow](../product-flow.md), especially task creation, retry/correction, recovery, lifecycle, and cross-feature rules.
- Existing OpenAPI `jobs`, `providers`, `assets`, `admin`, and common schemas.
- ADR-0002 modular monolith, ADR-0003 SQLite/SQLAlchemy/Alembic, ADR-0004 OpenAPI ownership, ADR-0005 single-instance runtime, ADR-0006 secrets, and ADR-0007 private storage.
- Completed Phase 2 persistence, authentication, private storage, resumable upload, asset/reference, Android recovery, and Web session foundations.

Authority remains: Product Spec for behavior, Product Flow for confirmed flow, Roadmap for phase boundaries, ADRs for architecture, and repository/tests for current implementation reality.

## Current State

- Phase 1 and Phase 2 are complete; the repository is a clean Git monorepo with Backend, Android, Web, contracts, CI, and deployment baselines.
- Jobs and Providers HTTP modules are contract-shaped stubs. No production job or provider behavior is wired.
- The OpenAPI contract already defines job/item states, job creation, cancellation, retry, requery, finish-failed, provider capabilities, and provider configuration operations. Phase 3 should close gaps additively instead of redesigning these resources.
- SQLite currently contains Phase 2 auth, idempotency, storage, upload, asset, reference, and audit tables. It has no job, output, provider configuration, snapshot, claim, or execution-event tables.
- `assets.kind` and the repository currently support only person/garment rows even though the contract includes `generated_output`; output persistence therefore requires a compatible schema/repository extension.
- The scheduler owns a process-level advisory lock but runs a `NoOpScheduler`. There is no durable claim, lease, retry, or recovery behavior.
- Private content-addressed storage, capacity checks, Unit of Work infrastructure, app/admin authentication, Problem Details, and idempotency records are reusable.
- No real LLM protocol, credentials, or vendor has been confirmed. The Roadmap explicitly permits a contract-level fake adapter for Phase 3.

## Implementation Delta

### NEW

- Provider configuration/version snapshots and default-provider persistence required to lock new jobs.
- `TryOnJob`, `JobItem`, `GeneratedOutput`, durable claim/lease, and execution-event persistence.
- Jobs and Providers domain/application ports, services, repositories, state-transition policy, and aggregate calculation.
- A single-instance polling scheduler with bounded claims, leases, retry/backoff, restart reconciliation, and storage-capacity admission.
- A deterministic fake image-edit Provider implementing the same port and contract tests required of future real adapters.
- Production job/provider HTTP handlers and Phase 3 integration/security verification.

### MODIFY

- Additive OpenAPI details, examples, problem codes, and generated clients where current schemas cannot express required Phase 3 behavior precisely.
- Asset persistence to support generated-output assets without weakening person/garment subtype invariants.
- Application lifecycle/configuration to replace the no-op runtime when scheduling is enabled.
- CI, environment template, backend/operator documentation, and roadmap/README progress.

### REUSE

- Existing auth dependencies, Problem Details envelope, cursor pagination, idempotency records, UoW pattern, storage capacity boundary, `LocalFileStorage`, `asset_references`, scheduler ownership lock, and generated-client pipeline.
- Existing public state names and command endpoints. Clients must not invent state transitions.

### EXCLUDED

- Real vendor credentials and a production LLM protocol adapter; these begin with the Phase 4 vertical slice once a vendor is selected.
- ComfyUI transport, node migration, Workflow JSON/bindings/activation, and locked Workflow compatibility checks; these belong to Phase 5.
- Android job screens and Web Admin provider-management UI; only their generated contract boundary may change here.
- Mask editing, quality-risk UI, cleanup policy UI, diagnostics UI, V1.1 Outfits, distributed workers, Redis/Celery/Kafka, PostgreSQL, or multiple application replicas.

## Technical Decisions

### Attempt lineage and aggregate state

- A `JobItem` is one immutable execution attempt for one candidate slot. Retry creates a new row with the same `candidate_index`, a strictly increasing `attempt`, and `retry_of_job_item_id`; it never overwrites the earlier attempt.
- Exactly one non-terminal attempt may be active for a candidate lineage. Constraints and application checks enforce this.
- Job aggregation is derived transactionally from candidate lineages: active work dominates; a successful replacement supersedes an older failed attempt for that candidate; retained failures remain visible in history; cancellation of one candidate does not alter another.
- `partially_succeeded` is a job aggregate only, never a `JobItem` state.

### Locked generation semantics

- Job creation resolves an active Provider configuration and persists an immutable snapshot of adapter type, model, semantic parameters, capabilities, and configuration revision. Encrypted credentials remain referenced through the Provider configuration and are never copied into snapshots or API responses.
- Default/provider changes affect only future jobs. Existing jobs use their locked configuration reference and snapshot.
- Workflow references remain nullable in Phase 3. No placeholder Workflow row or false compatibility guarantee is introduced before Phase 5.

### Durable claiming and leases

- The existing process ownership lock remains mandatory. Database claims add crash recovery, not multi-replica support.
- A claim uses one short atomic SQLite transaction with a claimant token, `claimed_at`, and `lease_expires_at`; external I/O never runs inside a database transaction.
- The scheduler uses bounded concurrency (default one), monotonic polling intervals, and persisted UTC retry times. Claim/lease constants are configurable non-secret settings with safe bounds.
- Expired `queued`, `waiting_provider`, or pre-submission `preparing` work may be reconciled. A previously `running` item is never blindly resubmitted.

### Provider port and error classification

- The Provider application port covers availability/capabilities, submit, query, cancel, and output retrieval. Transport details remain adapter-local.
- Errors are classified as: temporarily offline, retryable transient, invalid/permanent configuration, rejected input, externally ambiguous, and terminal execution failure.
- Offline maps to `waiting_provider` without consuming a retry budget. Retryable failures use persisted exponential backoff with bounded attempts. Configuration failures stop automatic execution. Ambiguous submit/query outcomes enter `needs_attention`.
- `JobItem.id` is the provider idempotency/correlation key. An adapter that cannot provide safe idempotency or reliable query semantics must surface ambiguity rather than permit automatic duplicate submission.

### Fake Provider boundary

- Phase 3 uses a deterministic in-process fake selected only by an explicit test/development adapter type. It produces valid normalized image bytes, stable execution IDs, controllable offline/transient/ambiguous/cancel outcomes, and no network calls.
- The fake is not available as a production provider unless an explicit non-production setting enables it. Production startup fails closed if a fake configuration is selected.
- All adapter-independent behavior is verified through a reusable Provider contract suite that future LLM and ComfyUI adapters must pass.

### Output and reference consistency

- Provider bytes are normalized and written through `LocalFileStorage`, then registered as a `generated_output` asset and `GeneratedOutput` row using the Phase 2 publish/compensation pattern.
- Input asset references are created in the same transaction as the job. They remain active while the job/history needs them; Phase 3 does not implement retention cleanup.
- Cancelled/obsolete late output is discarded and any newly written unreferenced object is compensated. It never becomes visible in job history.

### State transitions

- A centralized domain transition policy is the only owner of legal `JobItem` and job aggregate transitions.
- Commands are idempotent. Terminal items cannot be cancelled or resumed. `needs_attention` may be requeried, explicitly finished failed, or replaced by a new traceable retry attempt.
- State changes and safe execution events are persisted together. Events contain IDs, state, error code/class, and timing only—never tokens, Provider request bodies, source images, output bytes, or decrypted secrets.

## ADRs

Task 1 adds ADR-0008, documenting durable execution, lease/reconciliation, ambiguity, and provider-port rules. It extends ADR-0005 without authorizing horizontal scaling. No new infrastructure technology is introduced.

## Target Architecture

```text
App/API command
    -> Jobs application service
    -> Unit of Work
    -> jobs / job_items / asset_references / idempotency

Single-instance scheduler
    -> atomic durable claim
    -> Job execution service
    -> Provider port
    -> fake adapter (Phase 3) / real adapters (later)
    -> LocalFileStorage
    -> generated-output asset + output row
    -> state/event commit
```

The `Jobs` module owns job state and orchestration. `Providers` owns configuration, capability snapshots, adapter selection, and error normalization. Infrastructure implements SQLAlchemy repositories, scheduler polling, storage, encryption access, and concrete adapters; it does not own product state rules.

## Contract and Integration Strategy

- Keep the checked-in OpenAPI source authoritative and regenerate Backend/Android/Web clients together.
- Preserve existing operation IDs and state strings. Add only fields/responses needed for safe polling, lineage, blocked detail, and Provider configuration semantics.
- Phase 3 Backend implements all existing Jobs endpoints and the Provider configuration/list endpoints needed to create locked jobs. Web/Android generated clients compile, but their formal product UI remains unchanged.
- Tests use real SQLite migrations and private temporary storage. Unit tests may use in-memory fakes only at application-port boundaries.
- Contract examples cover queued, waiting, running, partially succeeded, needs-attention, cancelled, retry lineage, and late-result rejection.

## Tasks

### Task 1 — Close Phase 3 contracts and record execution semantics

Affected:

- `contracts/openapi/components/jobs/`, `contracts/openapi/components/providers/`
- `contracts/openapi/paths/jobs.yaml`, `providers.yaml`, and examples/problem codes
- generated Backend/Android/Web clients and contract boundary checks
- `docs/adr/0008-durable-job-execution.md`, ADR index

Work:

- Audit existing state, command, Provider, pagination, idempotency, and error schemas against the confirmed Phase 3 behavior.
- Make only additive corrections needed to express retry lineage, safe blocked/retry timing, immutable locked snapshots, and Provider error/availability semantics.
- Add examples for every important state and command result; ensure security and conflict responses are explicit.
- Record claim/lease, ambiguity, Provider port, single-instance, and no-blind-retry decisions in ADR-0008.
- Regenerate all consumers and strengthen contract checks so no platform defines local state/error variants.

Dependencies: Phase 2 complete.

Verify:

- OpenAPI lint/bundle/reference validation and generated drift checks pass.
- Backend generated typing and Android/Web generated clients compile.
- Contract tests prove state enums, command security, idempotency, error responses, and examples remain coherent.
- No ComfyUI/Workflow or V1.1 behavior is pulled into Phase 3.

### Task 2 — Add Phase 3 schema, migration, and repositories

Affected:

- Alembic Phase 3 revision
- database metadata, repositories, UoW, domain models, and persistence tests

Work:

- Add Provider configuration/revision/default-selection persistence with encrypted-secret references and immutable semantic snapshots.
- Add jobs, job-person inputs, job items, generated outputs, execution events, and claim/lease fields with foreign keys, indexes, checks, and UTC timestamps.
- Extend assets for `generated_output` while preserving exact subtype rules for person/garment and content-addressed reference counts.
- Add uniqueness for candidate attempts, external execution identity where safe, and one-active-attempt invariants enforceable in SQLite.
- Add repository/UoW ports and adapters for creation, listing, atomic claim, state compare-and-set, retry lineage, outputs, and events.

Dependencies: Task 1.

Verify:

- Empty database and Phase 2 database migrate to Phase 3 head; downgrade/re-upgrade passes.
- Constraint, index, UTC, foreign-key, rollback, concurrent idempotency, atomic claim, and generated-output reference tests pass.
- Migration preserves all Phase 2 tokens, sessions, uploads, assets, references, and stored objects.

### Task 3 — Implement Provider configuration, snapshots, and adapter contract

Affected:

- `modules/providers` domain/application/http packages
- secret encryption access and provider repositories
- fake adapter and reusable Provider contract tests

Work:

- Define Provider ports, request/result DTOs, capability/availability checks, and normalized error taxonomy.
- Implement create/read/update/validate/enable/list/default-selection Backend behavior required for new jobs, without building Phase 7 UI.
- Encrypt new credentials through the Phase 2 master-key facility; omitted secret input retains the prior secret and no read path returns it.
- Persist a new configuration revision for semantic changes and expose only redacted current configuration plus immutable refs.
- Implement deterministic fake availability, submit, query, cancel, and output retrieval scenarios behind an explicit non-production setting.

Dependencies: Task 2.

Verify:

- Provider contract suite passes for success, offline, transient, invalid configuration, rejected input, ambiguous state, cancellation, and late completion.
- Config revisions and default selection persist across restart; older refs remain readable.
- Secrets never appear in API responses, snapshots, logs, exceptions, fixtures, or generated bundles.
- Production configuration rejects fake adapter enablement.

### Task 4 — Implement the job state machine and aggregate policy

Affected:

- `modules/jobs/domain/`
- focused state-machine and property/table-driven tests

Work:

- Implement legal item transitions, terminal rules, block reasons, retry budget/backoff calculation, and cancellation markers.
- Implement candidate-lineage selection and job aggregate calculation across success, active work, failure, cancellation, and replacement attempts.
- Make time/random inputs injectable and keep domain behavior independent of FastAPI, SQLAlchemy, and Provider transports.
- Reject illegal transitions with stable application errors rather than repairing state silently.

Dependencies: Task 1; may proceed in parallel with Tasks 2–3 after contract closure.

Verify:

- Exhaustive transition tests cover every allowed and forbidden state edge.
- Aggregate tests cover 1–4 candidates, partial success, candidate cancellation, whole-job cancellation, retry replacement, and retained failed history.
- `waiting_provider` has no expiry and `partially_succeeded` never appears on a JobItem.

### Task 5 — Implement idempotent job creation and query APIs

Affected:

- Jobs application services and HTTP routes
- auth/idempotency/cursor adapters
- asset/reference and storage-capacity integration

Work:

- Replace list/create/get stubs with App-token authenticated handlers and contract responses.
- Validate person/garment/mask asset kinds and availability, candidate count, Provider state/capabilities, and storage admission before creating work.
- Resolve and lock Provider config revision/snapshot and nullable Workflow refs, then atomically persist the job, candidates, input references, and idempotency result.
- Allow temporarily offline Provider creation into `waiting_provider`; reject disabled, missing, incompatible, or invalid configurations without creating a job.
- Implement stable cursor ordering and authoritative nested item/output serialization.

Dependencies: Tasks 2–4.

Verify:

- Same idempotency key/request returns one job; changed or concurrent duplicate requests return the contracted result/conflict without duplicate candidates.
- Validation, scope, missing/deleted assets, reference creation, offline waiting, capacity block, and restart query tests pass.
- Changing the default/config after creation does not change locked job refs or snapshot data.

### Task 6 — Implement durable claiming, leases, and scheduler recovery

Affected:

- scheduler ports/runtime, application lifecycle/configuration
- Jobs claim/reconciliation services and repository queries
- scheduler tests and readiness diagnostics

Work:

- Replace the no-op scheduler with a polling loop that atomically claims dependency-satisfied items in deterministic order.
- Add bounded concurrency, lease renewal where needed, persisted backoff scheduling, shutdown coordination, and safe wake-up behavior.
- Leave storage-blocked jobs persisted in `queued`; resume automatically after capacity recovers.
- Reconcile startup/expired claims: recover safe pre-submission work, continue waiting work, and move uncertain prior running work to `needs_attention` unless query proves its state.
- Preserve the ADR-0005 process ownership guard and fail fast on a second owner.

Dependencies: Tasks 2 and 4.

Verify:

- Concurrent claim attempts produce one owner; lease expiry/reclaim is deterministic.
- Restart recovery tests cover queued, waiting, preparing, running, backoff, cancelled, and terminal items.
- No external call occurs within an open database transaction.
- Scheduler shutdown does not create a second submission or lose a committed transition.

### Task 7 — Execute jobs through the Provider port and persist outputs

Affected:

- Jobs execution service
- Provider registry/fake adapter
- `LocalFileStorage`, generated-output assets, compensation handling
- integration tests

Work:

- Assemble immutable Provider input from locked job snapshots and private input assets.
- Persist pre-submit state/correlation, call the Provider with `JobItem.id`, classify outcomes, and persist external execution identity before subsequent polling.
- Fetch successful bytes, normalize/store privately, create generated-output assets/rows, and publish state atomically with compensating cleanup.
- Recalculate aggregate state after every item transition or output publication.
- Detect cancellation/version changes before each stage and reject cancelled or obsolete late results.

Dependencies: Tasks 3–6.

Verify:

- Deterministic fake runs create private authenticated output assets and correct job/item states after restart.
- Multi-candidate success/failure and output metadata/seed/actual-parameter lineage are correct.
- Crash/fault injection around submit, fetch, file publish, database commit, and compensation creates neither duplicate visible output nor leaked referenced files.
- Logs contain no source/output bodies, decrypted secrets, or Provider request payloads.

### Task 8 — Implement candidate-level and whole-job cancellation

Affected:

- cancel application services and HTTP handlers
- scheduler/execution cancellation checks
- Provider cancel port and race-condition tests

Work:

- Replace cancel stubs with idempotent commands for one item or all unfinished candidates.
- Cancel queued/waiting work immediately; mark preparing/running work before best-effort Provider interruption.
- Preserve successful outputs, aggregate whole-job cancellation correctly, and discard/clean late results.
- Ensure cancelling one candidate cannot cancel or block unrelated candidates.

Dependencies: Task 7.

Verify:

- Cancellation tests cover every non-terminal state, unsupported Provider interruption, simultaneous completion/cancel, repeated commands, and restart.
- Whole-job cancel becomes `partially_succeeded` when any candidate succeeded and `cancelled` otherwise.
- Cancelled work is never submitted later and terminal commands return the contracted conflict/no-op semantics.

### Task 9 — Implement retry, requery, and needs-attention resolution

Affected:

- retry/requery/finish-failed application services and HTTP routes
- execution lineage, idempotency, and recovery tests

Work:

- Create a new candidate attempt for explicit retry while retaining the old item, error, external ID, event history, and possible cost evidence.
- Requery uncertain executions without submitting new work; synchronize known success/failure/running state through the Provider port.
- Allow explicit finish-failed only from `needs_attention` with retained reason/audit event.
- When a locked Provider version is unavailable, require an explicitly supplied compatible Provider for a new retry; never silently switch to the default.
- Recalculate the parent aggregate from candidate lineages after each command.

Dependencies: Tasks 7–8.

Verify:

- Retry produces a new ID/attempt and never updates the original item.
- Requery does not call submit; ambiguous requery remains stopped in `needs_attention`.
- Idempotent duplicate commands create at most one replacement attempt.
- Provider replacement is explicit, capability-checked, snapshotted, and visible in lineage.

### Task 10 — Add Phase 3 observability, operator boundaries, and CI gates

Affected:

- safe structured logging/readiness, Backend/infra README, `.env.example`
- verification scripts and `.github/workflows/ci.yml`
- roadmap and root README progress text

Work:

- Expose safe scheduler counts/status and blocked-state summaries without file paths, secrets, request bodies, or image data.
- Document polling/lease/backoff settings, single-owner operation, fake-adapter restrictions, restart reconciliation, and `needs_attention` operator rules.
- Add deterministic Phase 3 verification entry points and CI jobs for migrations, provider contracts, state machine, scheduler, job HTTP, security redaction, and generated drift.
- Update stale Phase 1/2 repository status documentation to match actual progress.

Dependencies: Tasks 1–9.

Verify:

- Logs and diagnostic responses are redacted and bounded.
- Environment/config documentation contains non-secret names/defaults only.
- CI fails on contract drift, illegal transition regression, duplicate claim/execution, migration failure, or credential/body leakage.

### Task 11 — Run the integrated Phase 3 exit gate

Affected:

- Phase 3 integration/security/fault-injection suites
- this plan's progress and roadmap delivery progress

Work:

- From a fresh Phase 2 database, migrate, initialize tokens/storage, configure and enable the fake Provider, create a job, execute candidates, retrieve private outputs, and restart/recover.
- Exercise duplicate creation, offline waiting/recovery, capacity blocking/recovery, transient backoff, cancellation, partial success, retry lineage, uncertain external state, requery, finish-failed, and late-result cleanup.
- Run the complete contract/backend/web-generated/android-generated/deployment boundary checks.
- Scan logs, database snapshots, reports, and bundles for credentials, decrypted Provider secrets, image bodies, and unsafe request payloads.
- Mark Tasks 1–11 complete only from captured fresh evidence.

Dependencies: Tasks 1–10 complete.

Verify:

- Every Phase Exit Checklist item below has automated evidence or a documented operator result.
- The Phase 3 verification command passes from a clean checkout with documented prerequisites.

## Phase Exit Checklist

### Contract and architecture

- [ ] Phase 3 contract additions are additive, generated without drift, and compile for Backend/Android/Web.
- [ ] ADR-0008 is accepted and consistent with ADR-0003/0005.
- [ ] Job state and Provider error semantics have one Backend owner and no platform-local variants.
- [ ] No Phase 4–9 UI, ComfyUI/Workflow, or Outfits implementation was pulled forward.

### Persistence and migration

- [ ] Empty and Phase 2 databases upgrade deterministically to Phase 3 head; downgrade/re-upgrade passes.
- [ ] Provider revisions, jobs, items, outputs, claims, events, and references survive restart.
- [ ] Atomic claim, candidate-attempt uniqueness, generated-output references, and rollback/compensation are verified.

### Job semantics

- [ ] Duplicate creation does not create duplicate jobs or execution.
- [ ] Provider config/model/capability snapshot is locked at creation and unchanged by later defaults.
- [ ] All item transitions and aggregate states match Product Spec, including partial success.
- [ ] Retry creates a traceable new item and preserves prior attempts.
- [ ] Candidate and whole-job cancellation preserve successful outputs and reject late results.

### Scheduler and recovery

- [ ] One scheduler owner atomically claims each item once with bounded leases/concurrency.
- [ ] Restart restores queued/waiting work and does not blindly resubmit uncertain running work.
- [ ] `waiting_provider` remains indefinitely until recovery or cancellation.
- [ ] Storage-blocked persisted work resumes only after safe capacity returns.
- [ ] Backoff is persisted, bounded, and excludes permanent/configuration failures.

### Provider boundary and outputs

- [ ] Fake adapter passes the reusable Provider contract suite and is production-disabled.
- [ ] Every Provider submission uses the internal JobItem correlation/idempotency identity.
- [ ] Ambiguous external state enters `needs_attention`; requery never submits new work.
- [ ] Outputs are normalized, privately stored, authenticated, referenced, and restart-safe.
- [ ] Secrets, bodies, and images are absent from logs, events, errors, reports, and API snapshots.

### Integration and operations

- [ ] Fresh local deployment can configure fake Provider, create/execute/query/cancel/retry jobs, and survive restart.
- [ ] CI covers migration, state machine, Provider contract, scheduler, job HTTP, generated clients, and redaction gates.
- [ ] Single-instance restriction remains enforced; no distributed queue or worker was introduced.
- [ ] Operator documentation explains safe recovery and `needs_attention` handling.

## Risks

- SQLite atomic claim and partial unique-index behavior must be validated against the pinned SQLite runtime, not assumed from another database.
- A crash between external acceptance and receipt persistence is the highest duplicate-cost risk. Adapters must use JobItem correlation and surface ambiguity conservatively.
- Database/file output publication cannot be globally atomic; compensation and restart reconciliation need explicit fault injection.
- Aggregate state can be subtly wrong when retries replace failed attempts. Candidate lineage tests must cover mixed old/new attempts rather than counting raw rows.
- Provider capability snapshots may become stale. They intentionally describe locked semantics; current availability is queried separately.
- The fake Provider proves orchestration, not vendor compatibility, output quality, pricing, or true cancellation. Phase 4 cannot claim a real vertical slice until one actual LLM adapter is verified.
- Aggressive polling or Argon2/image work can starve the single process. Keep scheduler concurrency bounded and all long work outside DB transactions.

## Upstream Conflicts

None identified.

The real LLM vendor/protocol remains an external Phase 4 input, not a Phase 3 blocker, because the Roadmap explicitly permits a contract-level fake adapter here. If implementation discovers that the existing contract cannot distinguish safe retry from ambiguous external execution, stop the affected task and route that behavioral conflict to Product Spec review rather than weakening the no-duplicate rule.

## Implementation Handoff

- Plan: `docs/plans/phase-3-durable-jobs-provider-core.md`
- Scope: Phase 3 only — durable jobs, Provider configuration/port, fake execution, state machine, scheduler recovery, cancellation, retry, and outputs.
- Start with: Task 1 — Close Phase 3 contracts and record execution semantics.
- Recommended scope: Task 1 only, then run its Verify section and review the OpenAPI/ADR boundary before creating the migration.
- Execution rule: implementation recovers progress from this file and repository reality, completes one high-risk task at a time, records verification/deviations, and does not enter Phase 4.

