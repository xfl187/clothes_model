# Local-first Asset Library Implementation Plan

status: implementation_complete  
updated: 2026-09-29  
planning_mode: FEATURE_PLAN  
depth: LARGE

## Goal

Implement the reviewed local-first person/garment library across Android, the OpenAPI contract, and the fixed Backend while preserving existing jobs, results, masks, and in-progress Phase 6 Android fixes.

Authoritative inputs:

- `docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md`
- `docs/product-flow.md`
- `docs/superpowers/specs/2026-09-23-android-v1-ui-design.md`
- `docs/changes/local-first-asset-library.md`

## Current State and Delta

- Android currently stages a Photo Picker file in app-private storage, immediately schedules an authenticated upload, records it in Room `pending-imports.db`, and deletes the staged file after upload succeeds.
- The asset center and creation wizard currently list Backend assets and load authenticated Backend thumbnails. They therefore cannot select materials when the Backend is unavailable.
- The draft stores Backend asset IDs and pending-import IDs, not durable local material IDs.
- Backend `assets` couple the logical asset row to one `stored_object_id`; upload completion always creates a new asset.
- Asset endpoints currently ignore the authenticated identity when listing/getting/updating/downloading assets. Upload sessions are token-owned, but assets have no stable owner independent of token rotation.
- Job creation adds active asset-reference rows, but terminal job completion does not currently release them for retention cleanup.
- The cleanup administration route is still a stub.

The required delta is a durable Android library, a stable owner scope, additive sync/rehydration contracts, safe legacy download migration, and automatic 24-hour Backend input-binary cleanup.

## Technical Decisions

1. **Stable ownership is separate from credentials.** Add a stable Backend `owner_scope` identity and associate App tokens with it. The current installation receives one migrated default owner. Rotating the App token preserves the same owner. Future accounts can create additional owner scopes without changing asset ownership semantics.
2. **Logical asset and binary availability remain separate.** Keep one Backend logical asset ID after its input binary is cleaned. Re-upload targets and rehydrates that owned logical asset rather than creating a duplicate library item.
3. **Android uses a durable local ID as its primary selection key.** Each local record stores server-instance ID, owner-scope ID, optional Backend logical asset ID, content hash, private-file path, metadata, quality/sync state, and timestamps.
4. **Preserve the existing Room file.** Evolve `pending-imports.db` with forward migrations and refactor its API toward a local-library database; do not destructively recreate it. Existing completed rows whose staged file was deleted are recovered by the server-to-device migration.
5. **Cleanup is scheduled data, not an ad-hoc timer.** Store cleanup eligibility/deadline in the Backend database. Terminal job transitions release job references and calculate the deadline transactionally; new active references clear it. A restart-safe cleanup service deletes only stored input bytes.
6. **No account UI in this feature.** Android persists and uses opaque server/owner identifiers returned by authentication status. It never shows account switching or cross-device sync controls.

## Progress

- Task 1 — COMPLETE (2026-09-29; contract lint/bundle/additive/boundary/mock and generated-client drift/type checks passed)
- Task 2 — COMPLETE (2026-09-29; owner scope migration + enforcement; two-owner isolation tests added)
- Task 3 — COMPLETE (2026-09-29; 24h cleanup service, acknowledged-copy gating, shared-object protection tests added)
- Task 4 — COMPLETE (2026-09-29; durable owner-scoped local library on `pending-imports.db` v5; JVM/file tests pass)
- Task 5 — COMPLETE (2026-09-29; `LegacyAssetMigrationWorker` downloads and acknowledges server-only materials)
- Task 6 — COMPLETE (2026-09-29; local-first startup/browse/selection; JVM tests + lint + assemble pass)
- Task 7 — COMPLETE (2026-09-29; submit-time upload/rehydration via `LocalAssetUploader`; JVM tests pass)
- Task 8 — COMPLETE (2026-09-29; local deletion protection and cleaned-copy detail states)
- Task 9 — COMPLETE_WITH_LIMITATION (2026-09-29; contract/backend/Android/Web deterministic gates pass; emulator/real-Backend device scenario deferred to CI/device run)

Current: All tasks implemented and committed. Deterministic release gates green; device instrumentation scenario remains the only deferred evidence.

## Verification Evidence (2026-09-29)

- Contract: `verify-generated.ps1` generated-artifact drift check passed (219 files); `verify-contract.ps1` passed lint, bundle, additive compatibility, phase 2/3/5/6 boundaries, local-first boundary, and Prism mock probes. Run under `pwsh` with `CI=true`.
- Backend: `ruff check .` clean; `pyright` 0 errors; `pytest` 113 passed including new `tests/test_local_first_library.py` (owner isolation across auth/assets/jobs, token-rotation owner stability, local-copy hash acknowledgement, active-reference byte protection, 24h deadline cleanup, unacknowledged legacy protection, shared stored-object dedup, cleaned-content rehydration).
- Android: `:core:api-contract:compileKotlin`, `:app:assembleDebug`, `:app:lintDebug`, `:app:testDebugUnitTest`, `:app:assembleDebugAndroidTest`, `:app:assembleRelease` all pass; `verify-release-boundary.ps1` passed. Connected instrumentation (`connectedDebugAndroidTest`) not run locally.
- Web Admin: `web:lint`, `web:typecheck`, `web:test`, `web:build`, and `check:bundle` production-credential scan all pass.

## Deviations

- Android persists the durable local library by evolving the existing `pending-imports.db` (Room v4→v5) rather than introducing a separate `LocalAsset` entity/table; the conceptual role is unchanged and the file name is preserved.
- Auth owner-scope access is exposed through new `OwnerScopeRepository`/`ServerIdentityRepository` ports instead of direct `uow.session` SQLAlchemy access in the application service.
- Terminal job transitions do not physically flip `asset_references.active`; cleanup eligibility and reference blocking derive terminal state dynamically by joining job state. Observable 24h-after-final-terminal behavior is preserved.
- Automatic cleanup is opt-in via `local_first_cleanup_enabled` (default `False`) and stays disabled until the new Android has acknowledged migrated content.

## Rollout Order

1. Deploy the additive Backend migration `20260929_0006` and Backend code first (older Android and Web clients remain compatible).
2. Keep `local_first_cleanup_enabled` disabled. Unacknowledged or legacy server-only assets are never auto-cleaned.
3. Roll out the new Android; on first authenticated run it migrates server-only person/garment originals locally and acknowledges a durable copy.
4. Only after migration recovery and acknowledgement tests pass on device, enable the cleanup scheduler.

## Tasks

### Task 1 — Extend the contract for identity, local-copy acknowledgement, and binary rehydration

Affected:

- `contracts/openapi/components/auth/schemas.yaml`
- `contracts/openapi/components/assets/schemas.yaml`
- `contracts/openapi/paths/assets.yaml`
- `contracts/openapi/paths/uploads.yaml`
- contract examples, generated clients, and boundary verification scripts

Work:

- Add stable `server_instance_id` and `owner_scope_id` to the authenticated App status response.
- Add Backend binary availability/sync metadata needed by Android without exposing storage paths.
- Add an owned rehydration target to upload creation, or an equivalent dedicated content-restore operation; require kind/metadata/content ownership consistency.
- Add an idempotent acknowledgement operation proving that an Android full file is durably stored and hash-verified.
- Keep all changes additive for older Android/Web clients and preserve unknown-enum handling.
- Regenerate Kotlin, Python, and TypeScript clients; do not hand-edit generated sources.

Verify:

- OpenAPI lint, bundle, additive compatibility, and generated-drift checks pass.
- Contract tests prove that owner identifiers are opaque, stable across token rotation, and present only after App authentication.
- Rehydration cannot target generated outputs, masks, another owner, or a mismatched kind/hash.

Dependencies:

- First task; it establishes boundaries required by Backend and Android work.

### Task 2 — Add Backend owner scopes and enforce them on every asset boundary

Affected:

- new Alembic migration after `20260928_0005_mask_assets.py`
- `backend/src/clothes_model/infrastructure/database/models.py`
- authentication domain/services/repositories and bootstrap/token rotation
- `backend/src/clothes_model/modules/assets/http.py`
- job input validation and payload reads
- authentication, asset, job, and migration tests

Work:

- Add an owner-scope table and foreign keys from App credentials and logical assets. Migrate all existing App assets/tokens into one default owner scope; Admin credentials remain administrative actors rather than material owners.
- Backfill ownership deterministically and keep token rotation attached to the same owner scope.
- Filter list/get/update/content/reference/delete/rehydrate operations by the authenticated owner. Return ordinary not-found behavior for cross-owner IDs to avoid existence disclosure.
- Require all person/garment/mask inputs in a created job to belong to the current owner and have available content.
- Persist a stable server-instance ID and expose it only through authenticated status.
- Add indexes supporting owner-scoped pagination and content lookup.

Verify:

- Forward migration preserves every existing asset, upload, job, and result.
- Tests with two synthetic owner scopes prove list/download/update/delete/job-create isolation.
- App token rotation retains access to the same owner’s materials; a different owner never gains it.

Dependencies:

- Depends on Task 1.
- Complete before Android begins owner-keyed persistence.

### Task 3 — Separate Backend logical assets from input bytes and implement 24-hour cleanup

Affected:

- Backend asset/storage schema and migration
- asset upload completion/rehydration logic
- job state-transition and reference repositories
- `backend/src/clothes_model/modules/cleanup/`
- scheduler/runtime wiring and storage/cleanup tests

Work:

- Add durable-copy acknowledgement and `cleanup_after` state for person/garment input content. Existing server-only assets begin unconfirmed and cannot be automatically cleaned.
- On ordinary local-first upload completion, verify content/hash, bind or rehydrate the owned logical asset, and acknowledge the durable Android copy idempotently.
- When a job enters a terminal aggregate state, release only its active job references. If no active job reference remains and a durable client copy is confirmed, set `cleanup_after = terminal_time + 24h`.
- When a new job references the asset, atomically clear `cleanup_after`; active `queued`, `waiting_provider`, `preparing`, `running`, and `needs_attention` jobs always protect bytes.
- Implement a restart-safe cleanup batch that rechecks ownership, content state, durable-copy confirmation, and active references before detaching/deleting the stored object. Preserve logical rows, job inputs, outputs, parameters, and lineage.
- Rehydrating content resets deleted/cleaned fields while keeping the same logical asset ID. Shared stored objects are physically removed only when no asset references them.
- Keep generated outputs, masks, workflow files, and their current configurable retention outside this fixed 24-hour rule.

Verify:

- State-transition tests cover success, partial success, failure, cancellation, and `needs_attention` resolution.
- Clock-controlled tests cover the 24-hour boundary, multiple jobs, countdown cancellation/restart, process restart, idempotent cleanup, and shared-object deduplication.
- Existing result/history and deleted-content placeholder tests remain green.

Dependencies:

- Depends on Task 2.
- Backend cleanup can be implemented in parallel with Android local persistence after schema/contract identities stabilize.

### Task 4 — Turn Android staging into a durable owner-scoped local library

Affected:

- `android/app/src/main/kotlin/com/clothesmodel/android/imports/`
- new or refactored local-library entities, DAOs, repositories, and file-store helpers
- `ConnectionStore`, authenticated identity persistence, Hilt bindings
- Room schema exports and migration tests

Work:

- Add a `LocalAsset` entity keyed by local UUID with server-instance/owner scope, private path, SHA-256, size/type, person/garment metadata, optional Backend asset ID, quality warnings, and explicit sync state.
- Copy Photo Picker content atomically into a permanent app-private library location; only publish the row after file fsync/hash verification succeeds.
- Stop deleting the permanent local original after upload. Restrict temporary files to incomplete copy/upload chunks.
- Refactor `PendingImport` into retryable sync-attempt state associated with a local asset. Migrate existing nonterminal staged rows without losing their files or WorkManager recovery.
- Preserve the existing database filename and supply forward migrations; prohibit destructive fallback.
- Store the authenticated server-instance and owner-scope identity. On identity mismatch, show only the matching local partition and stop background work for the old partition.

Verify:

- Room migrations cover every exported prior schema and both existing completed/nonterminal rows.
- File tests cover atomic copy, duplicate content, process death, missing/corrupt file, and cleanup of temporary—not permanent—files.
- Owner/server partition tests prove local records never leak into a different authenticated scope.

Dependencies:

- Depends on Task 1 identity fields; can proceed alongside Task 3 after those fields stabilize.

### Task 5 — Add safe one-time migration of existing server-only materials

Affected:

- Android WorkManager migration worker/coordinator
- local-library repository and authenticated content downloader
- Backend acknowledgement endpoint and migration-related tests
- connection and asset-center state models

Work:

- On the first authenticated run for a `(server_instance_id, owner_scope_id)` pair, page through owned person/garment assets whose content is available and no verified local mapping exists.
- Download each item into a temporary private file, verify hash/size where supplied, atomically promote it, create/update the local row, then acknowledge durability to the Backend.
- Make the worker resumable and idempotent; completed items are not downloaded twice.
- Pause on insufficient local space without acknowledging or deleting the server source. Stop immediately on 401 or owner/server identity change.
- Record aggregate progress and item-level recoverable failures for the UI. Do not migrate generated outputs or masks into the material library.

Verify:

- Tests cover interruption at every boundary, duplicate restart, pagination, 401, identity change, disk-full, corrupted download, and server content disappearing mid-migration.
- Backend cleanup tests prove unacknowledged legacy content cannot be deleted.

Dependencies:

- Depends on Tasks 2 and 4.

### Task 6 — Make startup, asset browsing, and images local-first

Affected:

- `android/.../navigation/AppNavigation.kt`
- `android/.../assets/AssetCenterViewModel.kt`, screens, detail, and image loading
- data repositories/mappers and connection UI
- relevant unit and Compose tests

Work:

- Enter the app shell and load the matching local library even when the Backend is unconfigured, offline, or requires reauthentication. Require connection only for server operations.
- Source person/garment grids and selection thumbnails from private local files. Continue using authenticated Backend loading for results/history.
- Compose local records with optional Backend metadata into UI models without treating temporary network failure as an empty library.
- Show only actionable sync states: not checked, syncing, ready, server copy cleaned, and local file missing.
- Add the nonmodal legacy-migration panel and preserve its state across process recreation.
- Keep future owner scope opaque; do not add account switcher UI.

Verify:

- Offline instrumentation tests can launch, browse/filter/select/import, and save a draft with the Backend stopped.
- Large-font, compact-width, TalkBack labels, and local image failure states pass.
- Existing history/result screens continue to use authoritative server data and reauthentication.

Dependencies:

- Depends on Tasks 4–5.

### Task 7 — Change the creation wizard to upload selected local assets only at submit

Affected:

- `android/.../create/CreateWizardViewModel.kt` and screen/logic
- `TryOnDraftStore`
- sync/upload worker and `JobRepository`
- wizard unit/instrumentation tests

Work:

- Store person/garment local IDs in the draft and restore them independently of Backend availability.
- Import into the local library and auto-select immediately; remove immediate upload scheduling from import actions.
- At submit, resolve each selected local item to a usable owned Backend logical asset: reuse available content, rehydrate cleaned content, or create the first logical asset upload.
- Show per-item upload/validation progress, retain one idempotency key per operation, and create the job only after both inputs are usable.
- On offline/401/upload/validation failure, retain local selections, settings, and draft. Cancel means cancel the sync/generation attempt, not delete the local material.
- Continue honoring Provider capability/configuration checks and `waiting_provider` semantics after input preparation succeeds.

Verify:

- Tests prove imports do not make network calls, repeated submission does not duplicate assets/jobs, cleaned copies rehydrate the same logical asset, and restart resumes safely.
- Compose tests cover offline call-to-action, per-item progress, validation warnings/blockers, cancellation, and successful navigation to the job.

Dependencies:

- Depends on Tasks 1, 4, and 6; full integration depends on Tasks 2–3.

### Task 8 — Implement local deletion protection and cleanup-aware detail states

Affected:

- Android asset detail/center state holders and screens
- local draft/reference queries
- Backend reference response usage
- deletion and accessibility tests

Work:

- Delete only the local file/record after explicit confirmation that explains history and lack of cloud backup.
- Block deletion when the material is selected by a saved draft or required by retained outfit data; list the removable/replacement reference rather than silently clearing it.
- Do not call Backend content deletion as a side effect of local deletion.
- Represent automatic Backend cleanup as “next generation will re-upload”, not as user deletion. If both local and Backend content are unavailable, show a stable unavailable state and replacement action.
- Preserve result deletion and server history behavior unchanged.

Verify:

- Tests cover unreferenced deletion, draft blocker, future outfit-reference adapter boundary, no Backend delete call, cleaned-copy status, and missing-both-sides recovery.
- Confirmation and blocker content remains usable at 200% font and with TalkBack.

Dependencies:

- Depends on Tasks 4, 6, and 7.

### Task 9 — Run migration, security, and end-to-end release gates

Affected:

- Backend/contract/Android verification scripts and CI
- README/operator notes and relevant plan progress

Work:

- Run contract generation/drift, Backend migrations/tests, Android Room migration/JVM/Compose tests, lint, and release assembly.
- Exercise an emulator scenario with the real Backend: import while offline, draft restore, reconnect, upload/create job, terminal completion, clock-controlled cleanup, and re-upload of the same local item.
- Exercise upgrade migration from existing server-only assets, including interrupted and disk-full recovery.
- Verify two synthetic owners cannot list, download, rehydrate, reference, or migrate each other’s materials.
- Verify logs, saved state, contracts, and diagnostics contain no token, private path, image bytes, or cross-owner identifiers beyond permitted opaque IDs.
- Document rollout order: deploy additive Backend/migration first, then Android; keep automatic cleanup disabled until the new Android has acknowledged migrated content.

Verify:

- Product Spec acceptance scenarios 38–43 have automated or recorded device evidence.
- Previous Phase 1–6 gates remain green.
- Rollback to the older Android remains safe because Backend contract additions are optional and unacknowledged assets are never auto-cleaned.

Dependencies:

- Depends on Tasks 1–8.

## Implementation Order and Checkpoints

Use small checkpoints because the work changes ownership and persistence:

1. Task 1, regenerate, verify contract.
2. Task 2, migrate and verify isolation.
3. Tasks 3 and 4 may proceed independently after their shared contract/schema assumptions are fixed.
4. Task 5 before enabling cleanup for legacy content.
5. Tasks 6–8 in order, then Task 9.

Do not enable the cleanup worker in a deployment until owner backfill, Android durable-copy acknowledgement, and migration recovery tests all pass.

## Risks and Rollback

- **Existing Android work is dirty:** preserve the current Phase 6 fixes in `CreateWizardViewModel`, `AssetCenterViewModel`, `PendingImportScheduler`, navigation, and tests. Implement by extending/reconciling those edits, not reverting them.
- **Irrecoverable input loss:** cleanup defaults off for legacy/unacknowledged assets and rechecks durable-copy confirmation immediately before delete.
- **Token rotation ownership drift:** assets belong to owner scope, never directly to a token ID.
- **Room migration loss:** retain the existing database file and every staged source; do not use destructive migration.
- **Mixed-version rollout:** Backend remains backward compatible; older Android continues immediate upload behavior, and its assets remain unacknowledged unless it can prove a durable local copy, so they are not auto-cleaned.
- **Rollback:** disabling the cleanup scheduler stops future binary removal without rolling back schema. Logical asset/history rows make already-cleaned content safe to display; same-device Android can rehydrate when its local original exists.

## Implementation Handoff

Plan: `docs/plans/local-first-asset-library.md`

Status: implementation complete; all tasks implemented and deterministic release gates pass. Follow the Rollout Order above.

Start with: none — implementation finished. Remaining evidence is the emulator/real-Backend device scenario, owned by a credentialed/device run or CI `connectedDebugAndroidTest`.

Recommended next scope: run the deferred device scenario when an emulator and the real Backend are available; do not enable automatic cleanup until migrated content is acknowledged on device.

Implementation preserved the pre-existing dirty Android/infra worktree and kept destructive cleanup disabled until the rollout gate is satisfied.
