# Defer ComfyUI Node Capabilities to V1.1

status: merged
updated: 2026-10-08
merged_into: docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md
affected_sections: Product Spec §§1–2, 4–7, 12–13, 15, 17–19; docs/product-flow.md; docs/acceptance/v1-acceptance-matrix.md
merged_date: 2026-10-08
next_action: Rebaseline the implementation roadmap and Phase 5/8/9 release records, then plan the smallest code/configuration gate needed to keep ComfyUI dormant in V1 and enable it in V1.1.

## Goal

Release V1 with the already verified direct-model generation path, and move the complete ComfyUI node
capability set and its production-readiness gate into V1.1.

## Current Behavior

- V1 promises both a direct-model Provider and one replaceable AutoDL ComfyUI node.
- V1 task creation allows a per-task direct-model/ComfyUI choice.
- V1 includes ComfyUI node configuration, immutable Workflow versions, validation, activation, rollback,
  offline `waiting_provider`, compatible-node replacement, recovery, and operator diagnostics.
- Real credentialed AutoDL/Comfy acceptance is currently a prerequisite for shipping V1 and V1.1 even
  though the implementation and deterministic gates are complete.
- V1.1 layered outfits reuse the Provider abstraction and require a Provider declaring
  `sequential_layering` and the target layer roles.

## Proposed Behavior

- V1 ships with the verified direct-model Provider as its production generation path.
- ComfyUI execution is not exposed as a selectable V1 generation backend and is not part of the V1
  production-readiness claim.
- The following capabilities move together to V1.1:
  - AutoDL/ComfyUI node configuration, connection testing, replacement, and readiness diagnostics;
  - immutable ComfyUI Workflow upload, binding, validation, activation, rollback, and version locking;
  - ComfyUI submission, polling, cancellation, output retrieval, temporary-file cleanup, and restart
    reconciliation;
  - ComfyUI-specific `waiting_provider`, compatible-node migration, and recovery operations;
  - Android and Web Admin surfaces that select, configure, diagnose, or recover a ComfyUI Provider;
  - real credentialed node/Workflow acceptance and the ComfyUI production-readiness claim.
- V1 retains the unified Provider boundary, versioned configuration model, and general durable-job states
  where they are also useful to the direct-model path. Existing implemented ComfyUI code may remain
  dormant behind capability/configuration gating; the version change does not require deleting it.
- V1.1 may enable ComfyUI for precise try-on and layered outfits after its real acceptance gate passes.
  Layered generation remains capability-driven and does not assume every ComfyUI Workflow supports
  `sequential_layering`.
- Shipping V1 no longer waits for a real AutoDL node or Workflow. Shipping the ComfyUI portion of V1.1
  still requires the existing credentialed acceptance evidence.

## User Flow

```text
V1: choose person and garment
    ↓
Use the available direct-model Provider
    ↓
Create, track, and view the result

V1.1: administrator configures and accepts a real ComfyUI node and Workflow
    ↓
ComfyUI becomes available where its declared capabilities match the requested task
    ↓
User may explicitly select it for precise try-on or layered outfits
```

## Affected Existing Behavior

- Product scope and success criteria must stop promising ComfyUI in V1.
- Android V1 creation must not show a ComfyUI override or ComfyUI-specific offline-wait messaging.
- Web Admin V1 release scope must exclude node and Workflow operations, while retaining the direct-model
  configuration and general operational surfaces.
- The V1 acceptance matrix must reclassify ComfyUI scenarios as V1.1 rather than deferred V1 release
  prerequisites.
- Phase 5 remains valid implementation history, but its product version ownership changes to V1.1.
- Phase 8 can represent a shippable direct-model V1 release without credentialed ComfyUI evidence.
- Phase 9/V1.1 release records must include both layered-outfit evidence and the deferred real ComfyUI
  node/Workflow gate.
- Existing task history and implemented ComfyUI data remain compatible; this change does not authorize
  deleting Provider, Workflow, job, or audit records.

## Failure / Recovery

- A V1 deployment without ComfyUI must not advertise ComfyUI capabilities or allow creation of a task
  that requires a ComfyUI Workflow.
- Existing development or migrated deployments containing ComfyUI configuration keep the data but do
  not treat it as V1 production-ready without the V1.1 acceptance gate.
- Direct-model failure, cancellation, retry, restart recovery, storage blocking, and `needs_attention`
  behavior remain in V1 where they are Provider-independent.
- V1.1 ComfyUI tasks keep the confirmed no-silent-switch, no-blind-resubmit, locked-Workflow, compatible
  node replacement, and late-result cleanup rules.

## Open Decisions

None identified. The requested version boundary is interpreted as moving the complete ComfyUI node and
Workflow product surface to V1.1 while preserving already implemented code and Provider-independent job
reliability in V1.
