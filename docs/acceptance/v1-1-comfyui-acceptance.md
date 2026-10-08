# V1.1 ComfyUI Acceptance Record

## Current status

- Deterministic implementation gate: **passed** on 2026-10-08 with `verify-phase9.ps1` and
  `CLOTHES_MODEL_PRODUCT_RELEASE=v1_1`.
- Credentialed AutoDL/ComfyUI production acceptance: **pending**.
- Effect on V1: none. The direct-model V1 gate is independent and does not expose ComfyUI surfaces.

## Deterministic evidence

The V1.1 gate proves that the logical Comfy Provider, node configuration, immutable Workflow lifecycle,
job locking, offline waiting/recovery, diagnostics, and layered-outfit paths remain available. The
release-boundary tests also prove the inverse V1 profile hides and rejects these product surfaces.

Relevant suites include `test_release_track_boundary.py`, `test_comfy_node_http.py`,
`test_workflow_lifecycle.py`, `test_job_workflow_locking.py`, `test_scheduler_recovery.py`,
`test_outfits_http.py`, and `test_outfits_layers.py`.

## Pending credentialed acceptance

Before enabling V1.1 ComfyUI in production, an operator must:

1. configure an authenticated real AutoDL/ComfyUI node;
2. validate and activate the intended immutable API-format Workflow;
3. execute and persist a bounded real output;
4. restart the Backend and prove prompt requery/output recovery without resubmission;
5. replace the physical node with a compatible node and prove waiting work resumes;
6. retain sanitized evidence for remote temporary-file cleanup and secret redaction.

Use the [node replacement](../runbooks/node-replacement.md) and
[Workflow publish/rollback](../runbooks/workflow-publish-rollback.md) runbooks. Do not claim V1.1
ComfyUI production readiness until this record is updated with dated operator evidence.
