# Runbook: ComfyUI node replacement

Goal: replace the single physical ComfyUI/AutoDL node without rewriting locked job configuration.

## Prerequisites

- A reachable replacement node with the models and custom nodes the active Workflow needs.
- Web Admin session.

## Procedure

1. Prepare the replacement node; do not stop the current node first if jobs are waiting.
2. Web Admin → `配置 / ComfyUI 节点` → edit endpoint/credentials/timeout.
3. Run the **connection test** (network/auth, ComfyUI API, node dependencies).
4. Run the **active-workflow trial** (verification rail). Enabling requires both to pass.
5. **Enable** the new node.

## Behavior

- Jobs lock the logical Provider revision and the exact Workflow version; the physical endpoint is never
  locked. A compatible replacement resumes `waiting_provider` work.
- Incompatible nodes leave waiting jobs waiting; they are not failed or silently re-pointed.
- Disabling/replacing a node never rewrites historical locked configuration.

## Expected signals

- Node health becomes `healthy`; active-workflow compatibility is `compatible`.
- Waiting jobs resume and complete; no resubmission of remotely finished work.

## Recovery

- Trial fails: keep the previous node or fix dependencies; the draft is retained.
- Node is offline: waiting jobs stay `waiting_provider` (never auto-cancelled) until a compatible node
  returns, or the user cancels.
