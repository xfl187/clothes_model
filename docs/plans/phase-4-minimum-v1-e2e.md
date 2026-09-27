# Phase 4 Implementation Plan

## Progress

- Status: IN PROGRESS
- Planning mode: PHASE_PLAN (LARGE)
- Current: Task 2 verified; Task 3 — paid Provider validation behavior
- Provider: Volcengine Ark `doubao-seedream-4-5-251128`
- Adapter type: `volcengine_ark_seedream`
- Task 1: COMPLETE — synchronous and asynchronous Provider completion paths verified
- Task 2: COMPLETE — canonical Seedream adapter and deterministic error mapping verified
- Task 3: IN PROGRESS
- Tasks 4–8: PENDING
- Next action: make explicit validation execute a synthetic one-image generation and discard it

## Goal

Deliver the first real V1 end-to-end vertical slice on a clean deployment:

`initialize tokens -> configure and validate Seedream in Web Admin -> authenticate Android -> upload one person image and one garment image -> create one-candidate job -> execute through Volcengine Ark -> persist the private output -> recover and display the result in Android`.

Phase 4 does not include ComfyUI/workflow lifecycle, mask editing, multiple candidates, the complete Android product, or the complete Web Admin operations surface.

## Confirmed Inputs

- [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 4 — Minimum V1 End-to-End Vertical Slice.
- [Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md), especially Android flow, durable execution, unified Provider, configuration, security, and acceptance scenarios.
- [Product Flow](../product-flow.md).
- [Android V1 UI Design](../superpowers/specs/2026-09-23-android-v1-ui-design.md).
- [Web Admin UI Spec](../superpowers/specs/2026-09-24-web-admin-ui-design.md).
- ADR-0004 contract ownership, ADR-0005 single-instance runtime, ADR-0006 secret protection, ADR-0007 private storage, and ADR-0008 durable Provider execution.
- Completed Phase 3 plan and repository implementation.
- User-confirmed Provider: Volcengine Ark `doubao-seedream-4-5-251128`.
- Official Volcengine references:
  - [Image generation API](https://docs.volcengine.com/docs/ark/image-generation-api?lang=zh)
  - [Model list](https://docs.volcengine.com/docs/ark/model-list?lang=zh)
  - [Base URL and authentication](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=zh)
  - [Ark error codes](https://docs.volcengine.com/docs/ark/error-codes?lang=zh)
  - [Model pricing](https://docs.volcengine.com/docs/LakeAIService/Largemodelbilling?lang=zh)

## Current Repository State

- Backend already owns Provider configuration revisions, encrypted credentials, validation/enable/default-selection behavior, durable jobs, scheduler leases, normalized execution errors, and private generated outputs.
- The Provider port assumes `submit -> query -> fetch`; the only executable adapter is the deterministic `fake_image_edit` adapter, and production rejects fake adapters.
- `JobExecutionService` currently calls the external side effect while the item is still `preparing`. That is unsafe for a synchronous paid API: a crash or connection loss after request transmission could cause a blind duplicate retry.
- The OpenAPI contract and generated Backend/Android/Web consumers already expose assets, uploads, jobs, Provider configuration, validation, enablement, default selection, and output retrieval.
- Android currently has connection/authentication, generated clients, and pending-import recovery foundations, but not the Phase 4 asset picker/upload, job submission/polling, or result screens.
- Web Admin currently has login/session protection and an engineering shell, but not the minimum Provider configuration and default-selection flow.
- Compose/Caddy, persistent SQLite/storage mounts, secret injection, and CI foundations exist; the deployment smoke gate does not yet exercise a real Provider or the Android/Web vertical slice.

## Provider Protocol Facts

- Data-plane base URL: `https://ark.cn-beijing.volces.com/api/v3`.
- Generation endpoint: `POST /images/generations` with `Authorization: Bearer <API key>`.
- Model ID: `doubao-seedream-4-5-251128`.
- Seedream 4.5 accepts multiple reference images, so the adapter sends the person image first and garment image second as Base64 data URLs plus an adapter-owned prompt.
- Phase 4 uses `sequential_image_generation: disabled`, `stream: false`, one generated image, and `size: 2K`.
- Phase 4 requests `response_format: b64_json`; outputs are decoded, normalized, and stored immediately. It does not depend on Provider URLs that expire after 24 hours.
- The API is synchronous for this mode and does not provide the durable query/cancel lifecycle required by asynchronous Providers.
- API Key authentication is used. The key is entered through Admin, encrypted by the existing master-key facility, never returned, never logged, and never written to repository configuration.

## Implementation Delta

### REUSE

- Shared OpenAPI ownership and generated consumers.
- Phase 2 authentication, resumable upload, asset metadata/reference, private storage, and Android import recovery.
- Phase 3 Provider configuration/revision services, task state machine, scheduler, output persistence, and recovery semantics.
- Existing Admin session shell, Android connection flow, Compose deployment, and CI conventions.

### NEW

- Production `volcengine_ark_seedream` adapter and HTTP transport.
- Synchronous-completion result support in the internal Provider port.
- Ark request construction, response decoding, capability declaration, error classification, and redacted diagnostics.
- Minimum Web Admin Provider configuration/validation/enable/default flow.
- Minimum Android asset selection/upload, single-candidate job, polling/recovery, and result flow.
- Phase 4 deterministic transport fixtures, optional credentialed smoke test, and clean-deployment runbook.

### MODIFY

- Move an async HTTP client into Backend runtime dependencies and lock it.
- Move the item to `running` before the first potentially billable network side effect.
- Make success persistence accept inline outputs as well as asynchronous fetch results.
- Expand test and CI boundaries without requiring paid credentials on ordinary pull requests.
- Update README/Roadmap progress after the Phase 4 exit gate.

### EXCLUDED

- ComfyUI nodes, workflow upload/versioning/activation, and physical-node recovery (Phase 5).
- Full Android task/history/result editing and multi-candidate experience (Phase 6).
- Full Web Admin diagnostics, storage, token, workflow, and operations surface (Phase 7).
- Automatic Provider fallback, distributed workers, push notifications, masks, and V1.1 layering.

## Technical Decisions

### Ark adapter identity and endpoint safety

- Use adapter type `volcengine_ark_seedream` and Provider type `llm_image_edit`.
- The production adapter accepts only the canonical HTTPS Ark data-plane host and `/api/v3` base path. Tests inject a fake transport directly rather than persisting arbitrary credential destinations.
- Reject unsupported model IDs for this Phase 4 adapter configuration; the first accepted model is exactly `doubao-seedream-4-5-251128`.
- Vendor parameters are allow-listed and normalized. Phase 4 exposes only bounded timeout and safe generation options needed by this slice; arbitrary request fields are not forwarded.

### Synchronous paid side effect

- Extend `ProviderSubmission` to represent either asynchronous acceptance or immediate completion with inline outputs.
- Persist `running` before calling `submit`. If the process dies or the connection outcome is unknown after transmission, restart reconciliation moves the item to `needs_attention`; it must not resubmit automatically.
- A successful synchronous response returns decoded inline output. `JobExecutionService` stores it through the existing normalization/publish path before marking the item `succeeded`.
- Seedream `query` cannot reconstruct remote state and remains conservatively ambiguous. Seedream `cancel` returns unsupported. A user can explicitly retry as a new attempt or finish an ambiguous item as failed.
- The fake adapter continues to exercise the asynchronous path so both execution shapes remain supported.

### Input and output mapping

- Send reference images in stable order: person first, garment second.
- Encode private inputs as in-memory Base64 data URLs; never expose private storage through public URLs.
- Build the prompt from an adapter-owned template plus normalized garment category/source. The template instructs the model to preserve identity, pose, body proportions, background, framing, and non-target clothing while replacing the target garment.
- Phase 4 supports one candidate only. Capabilities report `multiple_candidates=false`, `manual_mask=false`, `interrupt_running=false`, and output maximum `1`.
- Keep the Provider's default AI watermark enabled in Phase 4. Changing visible watermark behavior requires a later confirmed product/compliance decision.
- Store safe actual parameters such as model, requested size, response mode, and output dimensions; never store prompts containing user data, raw images, API keys, response bodies, or authorization headers.

### Validation and cost control

- Validation is an explicit Admin action and warns that it performs one billable minimal generation.
- Use bundled, synthetic, non-sensitive person/garment fixtures for validation; discard the generated validation output after decoding and structural checks.
- Configuration remains inactive until validation passes, then must be explicitly enabled and explicitly selected as default.
- Ordinary CI uses a scripted fake HTTP transport and never needs an Ark key. A credentialed smoke test is opt-in, limited to one generated image, and obtains its key from an external secret at runtime.

### Error mapping

- Missing/invalid credentials, service-not-open, permission, overdue-account, unsupported model, and persistent quota/configuration failures map to `invalid_configuration`.
- Input validation, unsupported image, payload-too-large, and input/output safety rejection map to `rejected_input` with safe user-facing detail.
- RPM/IPM limits, burst protection, server overload, and documented internal service failures map to bounded `retryable_transient` handling.
- Connection loss or timeout after transmission when no definitive Ark response was received maps to `externally_ambiguous`, not automatic retry.
- Logs and events may retain HTTP status, normalized Ark error code, latency, and a safe request identifier; they must not retain credentials, input/output bytes, full prompts, or raw bodies.

## ADRs

- Preserve ADR-0008 as the general execution contract.
- Add ADR-0009 for synchronous paid Provider calls, immediate outputs, pre-submit `running`, and ambiguity handling. This is a long-lived port decision shared by future synchronous adapters.

## Target Architecture

```text
Web Admin
  -> Provider config/revision API
  -> encrypted Ark API key
  -> explicit paid validation
  -> enable + set default

Android
  -> existing connection/token boundary
  -> resumable private uploads
  -> one-candidate job creation
  -> poll/recover job
  -> authenticated private result

Scheduler / JobExecutionService
  -> set running before side effect
  -> volcengine_ark_seedream adapter
  -> POST Ark /images/generations
  -> inline b64_json output
  -> normalize + private storage + GeneratedOutput
  -> succeeded / failed / needs_attention
```

## Contract and Compatibility Strategy

- Keep current public OpenAPI shapes unless implementation proves a real mismatch. The current Provider configuration, capability, job, upload, asset, and output schemas can express Phase 4.
- The synchronous-completion change is internal to the Backend Provider port; generated clients should not gain transport-specific fields.
- Preserve fake-adapter tests and all Phase 1–3 gates.
- Keep historical Provider snapshots immutable. Later changes to endpoint, model, prompt-template version, or vendor parameters create a new configuration revision.
- Record an adapter prompt-template version in safe actual parameters/config snapshots so output behavior is explainable without storing the full prompt.

## Tasks

### Task 1 — Close the synchronous Provider execution boundary

Affected:

- `docs/adr/0008-durable-job-execution.md`
- new `docs/adr/0009-synchronous-provider-completion.md`
- `backend/src/clothes_model/modules/providers/domain/invocation.py`
- `backend/src/clothes_model/modules/providers/application/ports.py`
- `backend/src/clothes_model/modules/jobs/infrastructure/execution.py`
- `backend/src/clothes_model/infrastructure/scheduler/jobs.py`
- fake adapter and Provider/scheduler/job tests

Work:

- Define asynchronous-accepted and immediate-completed submission results without leaking vendor protocol into job domain models.
- Transition a claimed item to `running` before the external side effect; retain `preparing` only for local input preparation that is safe to retry.
- Persist inline outputs through the existing normalized storage/asset/reference transaction path.
- Preserve async query/fetch behavior for the fake adapter and future ComfyUI work.
- Make crash/timeout recovery conservative and keep explicit retry lineage.
- Record the long-lived decision in ADR-0009 and align ADR-0008 wording.

Verify:

- Unit tests cover immediate success, async success, definite rejection, safe transient error, ambiguous timeout, crash before transmission, and crash after transition to `running`.
- Restart reconciliation never automatically resubmits a previously `running` synchronous call.
- Existing Phase 3 Provider contract, scheduler, command, and output persistence suites pass.

Dependencies and parallelization:

- Depends only on completed Phase 3.
- Must complete before Task 2. No UI task should assume the real Provider is executable before this boundary is verified.

### Task 2 — Implement the Volcengine Ark Seedream adapter

Affected:

- `backend/pyproject.toml` and `backend/uv.lock`
- new adapter/transport modules under `backend/src/clothes_model/modules/providers/infrastructure/`
- `backend/src/clothes_model/modules/providers/infrastructure/registry.py`
- `backend/src/clothes_model/api/application.py`
- `backend/tests/test_provider_contract.py`
- new Ark transport/error-mapping tests and sanitized JSON fixtures

Work:

- Promote a compatible async HTTP client to runtime dependencies and lock it.
- Implement canonical endpoint/model validation, Bearer authentication, bounded timeouts, Base64 data URLs, stable image ordering, prompt template, single-image non-stream request, and `b64_json` decoding.
- Return immediate-completion outputs and safe actual parameters.
- Implement capabilities, structural availability, unsupported query/cancel behavior, response-size bounds, content-type detection, and normalized Ark error mapping.
- Register the adapter in development and production while keeping fake adapters production-forbidden.
- Ensure the HTTP client is reusable and closed during application lifespan.

Verify:

- Mock-transport contract tests assert exact safe request shape and cover 200, malformed 200, 400 validation/safety, 401, 403, 413, 429 variants, 500, timeout-before-send, and ambiguous connection loss.
- Tests prove secrets, input images, output Base64, and raw prompt/body content do not reach logs or persisted diagnostic events.
- Backend lint, strict type check, unit tests, and Phase 3 gates pass without network access.

Dependencies and parallelization:

- Depends on Task 1.
- Task 3 can start after the adapter request/result/error surface is stable.

### Task 3 — Complete Provider validation and contract-facing configuration behavior

Affected:

- `backend/src/clothes_model/modules/providers/application/services.py`
- `backend/src/clothes_model/modules/providers/http.py`
- `contracts/openapi/components/providers/schemas.yaml`
- `contracts/openapi/paths/providers.yaml`
- `contracts/openapi/examples/providers.yaml`
- generated Backend/Android/Web consumers when source contracts change
- `backend/tests/test_provider_config_http.py`
- contract verification scripts

Work:

- Make validation execute one explicit, billable synthetic generation for the Ark adapter and report connection, credentials, model, capability, generation, and output-decode steps.
- Keep API keys write-only, preserve omitted-secret semantics on update, and prevent credentials from being sent to non-canonical hosts.
- Require successful validation before enablement and preserve explicit default selection.
- Add/adjust only contract details needed for cost warning and validation-step clarity; regenerate all consumers instead of editing generated files.
- Snapshot model, adapter, normalized vendor parameters, capabilities, and prompt-template version for new jobs.

Verify:

- HTTP tests cover create/update/validate/enable/default, failed paid validation, secret retention/rotation/redaction, idempotency, CSRF, and host/model rejection.
- Contract generation is drift-free and all generated consumers compile.
- No validation output or secret remains in storage, response payloads, logs, or test artifacts.

Dependencies and parallelization:

- Depends on Task 2.
- Tasks 4 and 5 may proceed in parallel after the public contract is stable.

### Task 4 — Build the minimum Web Admin Provider flow

Affected:

- `web-admin/src/app/router.tsx`
- `web-admin/src/app/AppShell.tsx` and shell styles
- new Provider gateway/state/pages/components under `web-admin/src/features/providers/`
- generated `ProvidersApi` and `AdminConfigurationApi` consumers
- Web unit and Playwright tests

Work:

- Add Provider list/create/edit screens constrained to Volcengine Ark Seedream for Phase 4.
- Collect display name, canonical endpoint, model, API Key, timeout, and safe vendor options; never re-display the secret.
- Show explicit cost confirmation immediately before validation, render per-step results and capabilities, then expose separate enable and set-default actions.
- Preserve unsaved-state, loading, retryable error, invalid-session, and narrow-screen behavior from the confirmed Admin UI spec.
- Update navigation labels from the engineering shell without implementing Phase 7 pages.

Verify:

- Unit tests cover validation flow, secret omission on edit, redaction, failure recovery, and default selection.
- Playwright covers login -> create -> cost confirmation -> validate -> enable -> set default with mocked deterministic APIs.
- Lint, type check, tests, production build, accessibility queries, and credential/bundle scan pass.

Dependencies and parallelization:

- Depends on Task 3 contract stability.
- Can run in parallel with Task 5.

### Task 5 — Build Android asset selection and durable upload

Affected:

- `android/app/src/main/kotlin/com/clothesmodel/android/app/ClothesModelApp.kt`
- existing `connection/` and `imports/` foundations
- new Phase 4 navigation, home, person/garment selection, upload gateway, and state holders
- Room schema/migration only if pending-import metadata must expand
- Android unit and instrumentation tests

Work:

- Route successful connection into the minimum home/create flow while preserving reauthentication behavior.
- Use Android Photo Picker/SAF, stage durable local copies, and extend existing WorkManager uploads rather than introducing a second upload path.
- Capture asset kind plus garment category/source metadata required by job creation; allow retry/cancel after process death without reopening the picker.
- Surface upload progress, validation failures, auth expiry, and safe cancellation.
- Keep the UI constrained to one person and one garment for Phase 4 while using existing list-shaped API contracts.

Verify:

- Unit tests cover state restoration, metadata validation, upload-to-asset mapping, and auth expiry.
- Instrumentation tests cover picker handoff with test URIs, Room migration when needed, WorkManager retry/cancel, and process recreation.
- Debug/release builds, lint, unit tests, instrumentation tests, and release-boundary checks pass.

Dependencies and parallelization:

- Depends on Task 3 contract stability and reuses Phase 2 upload behavior.
- Can run in parallel with Task 4. Task 6 depends on its asset IDs.

### Task 6 — Build Android one-candidate job, polling, recovery, and result display

Affected:

- new Android job/result gateways, state holders, screens, and navigation
- generated `ProvidersApi`, `JobsApi`, and `AssetsApi` consumers
- `ConnectionStore`/DataStore state for recoverable active job identity
- Android tests

Work:

- Load the default available Provider/capabilities, reject unavailable configuration before creating a job, and submit exactly one candidate with a unique idempotency key.
- Persist the active job ID, poll with bounded lifecycle-aware cadence, and resume from the server after navigation or process restart.
- Render confirmed queued/preparing/running/needs-attention/succeeded/failed/cancelled states without inventing client-local task truth.
- On success, retrieve the authenticated private output and display it with retry-safe loading/error handling.
- Preserve existing task execution when App authentication expires; reauthenticate and resynchronize instead of cancelling it.

Verify:

- Unit tests cover creation idempotency, every Phase 4 state mapping, polling cancellation, restart recovery, auth expiry, and private output failure.
- Instrumentation tests cover upload completion -> create -> poll -> success -> result and activity/process recreation with a deterministic contract server.
- Android quality gates remain green.

Dependencies and parallelization:

- Depends on Task 5 and Task 3.
- Can integrate against mocked Provider responses before Task 7 real smoke credentials exist.

### Task 7 — Add deployment, observability, and bounded-cost smoke verification

Affected:

- `.env.example`
- `infra/compose.yaml`
- `infra/README.md`
- new `infra/verify-phase4-deployment.ps1`
- `.github/workflows/ci.yml`
- Backend logging/metrics tests where needed
- operator documentation

Work:

- Document canonical Ark endpoint/model, model activation, API Key injection through Admin, validation cost, and safe rotation/revocation.
- Keep the API Key out of Compose environment and source files; only the existing encryption master key is a deployment secret.
- Add deterministic no-network Phase 4 gates to normal CI.
- Add a manually dispatched credentialed smoke path guarded by environment secrets and an explicit one-image budget; never run paid generation on pull requests.
- Extend the clean-deployment script through token initialization, Provider configuration/validation/enable/default, private uploads, one job, restart/recovery, and authenticated output retrieval.
- Capture only redacted statuses, normalized error codes, latency, job/item IDs, and output hashes/sizes in reports.

Verify:

- Compose config and production single-instance boundaries still pass.
- Static scans find no Ark key, Authorization value, Base64 image, or full prompt in repository, images, logs, artifacts, or Web bundles.
- Deterministic deployment smoke passes without network; the opt-in credentialed run produces at most one image and persists it locally.

Dependencies and parallelization:

- Depends on Tasks 2–6.
- Documentation can begin earlier, but the final script and workflow wait for all integration surfaces.

### Task 8 — Run the integrated Phase 4 exit gate

Affected:

- all Phase 4 suites and smoke scripts
- `README.md`
- `docs/roadmap/implementation-roadmap.md`
- this plan's progress and checklist

Work:

- Run contract generation/drift checks, Backend lint/type/tests, Web lint/type/tests/build/E2E, Android compile/lint/unit/instrumentation, deployment smoke, secret scans, restart recovery, and one credentialed Seedream generation.
- Manually verify the confirmed Android and Web minimum flows on a clean deployment.
- Record prerequisites, tool versions, sanitized evidence, cost-bounded invocation count, and any deviations.
- Mark Phase 4 complete only after the real Provider output is privately persisted and recoverable from Android.

Verify:

- Every checklist item below has automated evidence or a documented operator result.
- Phase 1–3 gates remain green.
- README and Roadmap agree on current phase and next action.

Dependencies and parallelization:

- Depends on Tasks 1–7.
- This is the final Phase 4 task and must not pull Phase 5 implementation forward.

## Phase Exit Checklist

### Provider and execution safety

- [ ] `volcengine_ark_seedream` is production-registered for exactly the confirmed model/host boundary.
- [ ] Person and garment images are sent privately as Base64 data URLs in stable order.
- [ ] One Seedream output is decoded, normalized, privately persisted, and detached from Provider retention.
- [ ] Synchronous side effects enter `running` before transmission; unknown outcomes never auto-resubmit.
- [ ] Ark errors map to configuration, rejected-input, transient, terminal, or ambiguous classes with no secret/body leakage.
- [ ] Query/cancel limitations are visible and conservative.

### Web Admin

- [ ] Admin can create/update a redacted Ark config, explicitly accept one-image validation cost, validate, enable, and set default.
- [ ] API Key is encrypted at rest, write-only over the contract, omitted on edit unless replaced, and absent from logs/bundles.
- [ ] Failed validation cannot enable the Provider or silently change the default.

### Android

- [ ] User can connect/authenticate, select one person and one garment, survive upload interruption, and obtain persistent asset IDs.
- [ ] User can create a one-candidate job and see server-authoritative progress and failures.
- [ ] Leaving/restarting the app restores the active job and authenticated private result.
- [ ] Token expiry preserves server work and recovers after reauthentication.

### Deployment and verification

- [ ] Clean deployment completes the confirmed token -> Admin -> Android -> Ark -> private storage -> Android loop.
- [ ] Tasks, assets, Provider snapshot, and output have persistent IDs and survive Backend restart.
- [ ] Normal CI is deterministic and free; the paid smoke is manual, secret-gated, and capped at one image.
- [ ] Phase 1–3 regression, generated-drift, release-boundary, single-instance, and secret-redaction gates pass.

## Risks

- Seedream is a general multi-reference image generation model, not a dedicated virtual try-on protocol. Phase 4 proves integration and the minimum product loop, not garment fidelity; acceptance must inspect identity, pose, garment, and background preservation.
- The synchronous endpoint has no durable status query. A connection loss after transmission may consume cost without a recoverable result; conservative `needs_attention` behavior is mandatory.
- Base64 request/response bodies can be large. Bound decoded size, encoded size, timeouts, memory use, and concurrency; do not hold DB transactions during network or image work.
- Provider validation is billable. UI confirmation and one-image smoke limits prevent accidental repeated costs.
- Ark limits and error codes can evolve. Keep mappings explicit, preserve unknown codes safely, and recheck official documentation during implementation.
- Prompt-template changes alter generation semantics. Version the template and create a Provider configuration revision rather than silently changing locked jobs.

## Migration and Rollback

- No database migration is expected for the Provider adapter itself. If Android pending-import metadata expands, add and test a Room migration that preserves existing staged imports.
- The adapter is additive. Rollback disables the Ark configuration/default and deploys the prior application; existing jobs and outputs remain readable.
- Jobs already submitted through Ark retain their locked configuration snapshot. Rollback must not rewrite them or silently route them to the fake adapter.
- Never delete stored outputs or encrypted configuration during rollback. Credential revocation is performed in Volcengine and then the local config is disabled/rotated.

## Upstream Conflicts

None identified. The selected Provider satisfies the Phase 4 need for multi-reference image generation, but quality remains an exit-gate observation rather than an unconfirmed product guarantee.

## Implementation Handoff

- Plan: `docs/plans/phase-4-minimum-v1-e2e.md`
- Scope: Phase 4 only — one real Volcengine Ark Seedream vertical slice across Backend, minimum Web Admin, minimum Android, and deployment verification.
- Start with: Task 1 — Close the synchronous Provider execution boundary.
- Recommended implementation scope: Task 1 only, then run its Verify section and review ADR/duplicate-cost safety before Task 2.
- Prerequisites for Task 1: none beyond the completed Phase 3 repository.
- Credential prerequisite: not needed for Tasks 1–6 deterministic work; Task 7's opt-in real smoke requires an Ark API Key supplied through a secure local/CI secret, never through chat or Git.
- Execution rule: recover progress from this plan and repository reality, record material deviations, preserve confirmed product/UI behavior, and do not enter Phase 5.
