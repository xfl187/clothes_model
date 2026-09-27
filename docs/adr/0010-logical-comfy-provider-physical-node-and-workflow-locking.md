# ADR-0010: Logical Comfy Provider, replaceable physical node, and Workflow locking

- Status: Accepted
- Date: 2026-09-28

## Context

The Product Spec requires one replaceable AutoDL/ComfyUI physical node, immutable Workflow versions, and jobs that can wait indefinitely while the node is offline. A compatible replacement node must be able to continue waiting work, but changing a default, endpoint, credential, or active Workflow must never rewrite a historical job.

The Phase 3 Provider model already gives every job an immutable Provider configuration revision and allows an optional Workflow snapshot. Treating the physical ComfyUI endpoint as an ordinary locked Provider endpoint would violate node-replacement behavior: a waiting job would remain tied to the retired host. Conversely, resolving only the latest active Workflow at execution time would silently change generation semantics for an existing job.

ComfyUI also exposes an implementation-facing server protocol rather than a product-level durable-job API. The official server currently provides image upload, prompt submission, queue/history lookup, output viewing, pending queue deletion, and interruption of current execution. Pending deletion and current interruption do not provide the same certainty or scope. The protocol can evolve and must remain isolated behind the Provider adapter.

## Decision

### Separate semantic identity from physical execution location

- Keep a stable, selectable logical Comfy Provider in the existing `ProviderConfig`/revision model.
- The logical revision snapshots adapter semantics and Workflow-derived capabilities. It does not contain the replaceable physical node endpoint or credential.
- Store the singleton physical node endpoint, encrypted credential, timeout, enablement, observed server version, and health separately as `ComfyNodeConfig`.
- Default-Provider selection targets the logical Provider identity. Replacing or disabling the physical node does not change that identity and does not rewrite jobs.

### Lock the Workflow, resolve the node

- A Comfy job locks both its logical Provider revision and exact immutable Workflow version when the job is created.
- The Workflow snapshot includes stable identity/version plus canonical Workflow and manifest digests. Provider capabilities in the job snapshot reflect that locked Workflow.
- At execution or recovery time, the adapter resolves the current physical node and checks it against the locked Workflow's required nodes, bindings, outputs, and capabilities.
- A compatible node may execute or resume the job. An offline node leaves the job in `waiting_provider`. A reachable but incompatible node also cannot execute the job and exposes an actionable compatibility conclusion without changing the snapshot.
- Activating, retiring, or rolling back a Workflow affects new jobs only. Rollback is activation of a previously validated/retired immutable version.

### Preserve external-execution truth

- Persist the Comfy prompt identifier as the external execution identity immediately after accepted submission.
- Query queue/history by that identity before deciding whether work is queued, running, succeeded, failed, or unknown.
- A connection loss after a possible submission is ambiguous unless the accepted prompt can be correlated and queried. Ambiguous work enters `needs_attention`; it is never resubmitted automatically.
- Pending queue deletion and current execution interruption are best-effort operations. Local state becomes cancelled only when the normal state machine and external evidence permit it. Uncertain interruption does not masquerade as confirmed cancellation.
- Remote filenames, subfolders, content types, JSON fields, and response sizes are untrusted. Only outputs declared by the locked manifest may be fetched and published.

### Pin and test the protocol

- Implement against a pinned, tested ComfyUI server revision or image, not a floating third-party SDK.
- Keep protocol paths and response parsing inside the Comfy adapter/client.
- Normal CI uses a deterministic local fixture covering upload, submit, queue/history, output retrieval, pending deletion, interruption limitations, malformed responses, and ambiguity.
- A bounded opt-in operator test verifies the intended authenticated AutoDL/Comfy environment.

The upstream protocol evidence used for this decision is the official [ComfyUI server implementation](https://github.com/Comfy-Org/ComfyUI/blob/master/server.py) and official [server route documentation](https://github.com/Comfy-Org/docs/blob/main/zh/development/comfyui-server/comms_routes.mdx). These links describe the upstream boundary; repository tests and the pinned revision define the supported runtime contract.

## Consequences

- Historical jobs retain stable generation semantics while operators can replace failed or expired AutoDL nodes.
- Node reachability and Workflow compatibility are separate conclusions; a healthy endpoint is not automatically usable.
- The Comfy adapter needs access to both a locked Workflow resolver and the current singleton node resolver, unlike ordinary endpoint-owning Provider adapters.
- Activating a Workflow creates or selects a new logical Provider capability revision for future jobs without mutating previous revisions.
- Recovery can safely resume known prompts and compatible waiting work, but uncertain prompts stop for explicit requery/retry/fail handling.
- Phase 5 adds persistence for node configuration and Workflow artifacts while preserving null Workflow references on pre-Phase-5 jobs.
- Full node and Workflow management UI remains Phase 7; Phase 5 provides the shared API and execution semantics.

## Rejected alternatives

### Lock the physical endpoint in each job

Rejected because replacement nodes could not resume waiting jobs without rewriting history or silently switching configuration.

### Resolve the currently active Workflow at execution time

Rejected because activation or rollback would change already-created jobs and could alter cost, inputs, outputs, or generation meaning.

### Automatically resubmit when Comfy state is unknown

Rejected because it can duplicate GPU work, outputs, and cost. Duplicate avoidance takes priority over automatic progress.

### Introduce multiple nodes or a distributed worker queue in V1

Rejected because the confirmed scope is one replaceable node and the deployment remains single-instance. Multi-node scheduling is a future architecture decision.
