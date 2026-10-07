# Runbook: Workflow publish and rollback

Goal: publish an immutable ComfyUI Workflow version, activate it for new jobs, and roll back safely.

## Prerequisites

- Single ComfyUI node configured and reachable ([node replacement](node-replacement.md)).
- API-format Workflow JSON and its manifest (bindings, declared outputs, capabilities).

## Procedure

1. Web Admin → `配置 / Workflows` → upload the API JSON and version metadata; the version is created as
   an immutable `draft`.
2. Run validation: it performs structural checks and a bounded minimal trial run against the current
   node, then marks the version `validated` with recorded results.
3. **Activate** the validated version. Activation atomically retires the prior active version for that
   mode and only affects jobs created afterwards.
4. To roll back, activate a previously `validated`/`retired` version; the same impact rules apply.

## Expected signals

- Validation reports ordered checks and a compatibility result.
- After activation, the overview effective-configuration band shows the new active Workflow version.
- New jobs record the new version; existing jobs keep their locked version and digests.

## Recovery

- Validation fails: fix the Workflow → the version stays `draft` with diagnostics.
- Activate fails with a stale-reference conflict: refresh the list and retry with the current active id.
- Never edit an activated version in place; upload a new immutable version.
