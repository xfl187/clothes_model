# ADR-0008: Durable job execution, leases, and provider ambiguity

- Status: Accepted
- Date: 2026-09-27
- Extends: ADR-0005 (does not authorize horizontal scaling)

## Context

Phase 3 makes try-on work durable: a `TryOnJob` and its candidate `JobItem` rows are persisted before execution, then claimed, executed, cancelled, retried, and recovered across restarts. V1 keeps the ADR-0005 single-instance runtime with SQLite and an in-process scheduler.

External generation has failure modes that a naive worker loop corrupts: a provider can be temporarily offline, throttle transiently, reject input permanently, or accept a request whose outcome becomes unobservable after a crash. Blindly resubmitting ambiguous work can duplicate real cost. The contract must therefore let the Backend distinguish safe retry from uncertain external state, and clients must observe exactly one Backend-owned state and error vocabulary.

## Decision

### Single owner and durable claims

- `TryOnJob` and `JobItem` state is persisted; the scheduler runs in the single application process and must keep the ADR-0005 instance lock.
- A claim is one short atomic SQLite transaction that records a claimant token, `claimed_at`, and `lease_expires_at`. No external I/O runs inside a database transaction.
- Concurrency is bounded (default one) and polling intervals are monotonic. Claim, lease, and backoff constants are non-secret configuration with safe bounds.
- Duplicate creation is prevented by persisted job/idempotency records. A duplicate or concurrent request returns the original job or the contracted conflict; it never creates duplicate candidates.

### Job identity and provider correlation

- `JobItem.id` is the provider idempotency and correlation key for every submission, query, cancellation, and output retrieval.
- An adapter that cannot guarantee safe idempotency or reliable status query must surface that ambiguity instead of permitting automatic duplicate submission.
- Exactly one non-terminal attempt may be active per candidate lineage. Retry creates a new `JobItem` with the same `candidate_index`, a strictly increasing `attempt`, and `retry_of_job_item_id`; the earlier attempt is retained for history, error, and cost evidence.

### Provider port and normalized error classes

The Provider application port exposes availability/capabilities, submit, query, cancel, and output retrieval, with transport specifics kept adapter-local. A submission can either be asynchronously accepted with a durable external identifier or synchronously completed with inline output bytes; see ADR-0009. Adapters classify outcomes into:

- temporarily offline;
- retryable transient;
- invalid/permanent configuration;
- rejected input;
- externally ambiguous;
- terminal execution failure.

Mapping rules:

- Offline maps to `waiting_provider` and does not consume the retry budget.
- Retryable failures use persisted UTC exponential backoff with bounded attempts; the next attempt time is exposed to clients.
- Configuration failures stop automatic execution and never auto-retry.
- Ambiguous submit or query outcomes enter `needs_attention`.
- `waiting_provider` does not expire; it ends only on recovery or cancellation.

Requery reads external state through the Provider port and never submits new work. Ambiguous requery leaves the item in `needs_attention`.

### Locked generation semantics

- Job creation resolves an active Provider configuration and persists an immutable snapshot of adapter type, model, semantic parameters, capabilities, and configuration revision.
- Encrypted credentials remain referenced through the Provider configuration and are never copied into snapshots, events, or API responses.
- Changing the default provider, model, or active workflow affects only future jobs. Existing jobs keep their locked configuration reference and snapshot; an unavailable locked version enters `needs_attention` rather than silently falling back.

### Output and reference consistency

- Provider bytes are normalized and written through the Phase 2 `FileStorage`, then registered as a `generated_output` asset and `GeneratedOutput` row using the publish/compensation pattern.
- Input asset references are created in the same transaction as the job.
- Late results for cancelled or superseded work are discarded and any newly written unreferenced object is compensated; they never become visible in job history.

### Single state and error authority

- A centralized Backend domain policy is the only owner of legal `JobItem` and aggregate transitions. Clients issue commands and render states; they do not invent transitions or error variants.
- State changes and safe execution events are persisted together. Events contain IDs, state, error code/class, and timing only, never tokens, provider request bodies, source images, output bytes, or decrypted secrets.
- `partially_succeeded` is a job aggregate only and never a `JobItem` state.

## Consequences

- Restart can recover `queued`, `waiting_provider`, and safe local-only `preparing` work, while previously `running` work is never blindly resubmitted. The item enters `running` before the first external side effect.
- Ambiguity trades automatic progress for cost safety: uncertain work stops in `needs_attention` for an explicit requery, retry, or finish-failed decision.
- The Provider contract suite is adapter-independent and must be passed by the Phase 3 fake adapter and every future LLM or ComfyUI adapter.
- V1 remains single-instance. Horizontal scaling still requires a later ADR that replaces the persistence and claim model; adding replicas or workers alone is unsupported.
- The fake adapter proves orchestration only. A real vendor vertical slice still belongs to Phase 4.
