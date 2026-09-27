# ADR-0009: Synchronous Provider completion and paid side-effect boundary

- Status: Accepted
- Date: 2026-09-27
- Extends: ADR-0008

## Context

ADR-0008 originally described Providers as submit/query/fetch lifecycles. Volcengine Ark Seedream's non-stream image-generation API completes synchronously: the request may incur cost and returns output bytes in the same response, without a durable execution resource that can later be queried or cancelled.

If the Backend calls such an API while a `JobItem` is still `preparing`, a crash or connection loss after transmission makes the outcome uncertain. Restarting `preparing` work would blindly repeat a potentially paid generation.

## Decision

- `ProviderSubmission` explicitly represents either asynchronous acceptance or synchronous immediate completion.
- The Backend persists `running` before the first potentially billable external side effect. `preparing` is reserved for local work that is safe to repeat.
- A synchronous success returns inline `ProviderOutput` values. The existing output normalization, private storage, asset registration, and reference transaction persists them before the item becomes `succeeded`.
- A synchronous adapter without a durable vendor execution resource does not invent a queryable remote ID. Query and cancellation remain unsupported and conservative.
- A connection loss, timeout after possible transmission, or restart from `running` enters `needs_attention`. Automatic retry is forbidden; explicit retry creates a new attempt with lineage.
- Definite pre-acceptance rejection and documented transient responses may use existing normalized error handling because the Provider supplied an authoritative response.

## Consequences

- Both asynchronous Providers and synchronous Providers share one port without pretending their recovery guarantees are identical.
- The state visible during a long synchronous call is `running`.
- Cost safety takes priority over automatic progress when the synchronous outcome is unknown.
- Future synchronous adapters must pass the immediate-completion and ambiguity contract tests.
