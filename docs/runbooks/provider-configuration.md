# Runbook: Provider configuration

Goal: maintain one active LLM (or ComfyUI) Provider safely and select the default for new jobs.

Release scope: V1 permits direct-model LLM Providers only. ComfyUI configuration and selection require
`CLOTHES_MODEL_PRODUCT_RELEASE=v1_1`.

## Prerequisites

- Web Admin session (Admin Token).
- For paid tests: confirmation that a real generation may incur cost.

## Procedure

1. Web Admin → `配置 / LLM Provider` → create or edit a configuration (identity/protocol, endpoint, model,
   timeout, overwrite-only API key, vendor parameters).
2. Run the **free connection test** first; it verifies reachability/protocol without spending credit.
3. Run the **paid minimal generation test** only when intended; it confirms end-to-end generation and
   enables the `validated` state.
4. **Enable** the configuration, then choose it in `配置 / 默认后端`. Saving, validating, enabling, and
   defaulting are independent actions.
5. Archive instead of deleting when history exists; restore returns the Provider to `inactive` and it must
   be validated and enabled again.

## Expected signals

- Connection test shows ordered steps (`credentials`, `connection`, `capabilities`).
- The default-backend page shows the new default and notes that it only affects new jobs.

## Recovery

- Connection test fails: fix endpoint/credentials; the current effective configuration and its locked jobs
  are untouched.
- Archived Provider: restore, re-validate, re-enable; existing jobs keep their locked revisions.
- Permanent delete is refused while history exists; archive instead.
