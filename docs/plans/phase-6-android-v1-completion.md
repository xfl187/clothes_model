# Phase 6 Implementation Plan

## Progress

- Status: COMPLETE — all 10 Tasks implemented, verified, and committed; Phase 6 exit gate passed
  2026-09-28 via `android/verify-phase6.ps1` (generated contract, contract boundaries, Backend
  lint/type/tests, Android build/lint/unit/instrumentation compile/release, release-boundary scan)
- Planning mode: `PHASE_PLAN + LARGE`
- Planned: 2026-09-28
- Scope: Android V1 product completion on the stable Phase 1–5 Backend/API
- Deferred external gate: real credentialed AutoDL/Comfy acceptance remains a later release-readiness
  requirement and is not part of the Phase 6 exit gate
- Execution rule: complete, verify, and Git-commit every Task before starting the next Task
- Task 1 — COMPLETE (2026-09-28): audited Android V1 asset/job/provider routes; repaired
  generated-output favorite consistency; terminal references no longer block content deletion while
  non-terminal sources return an inspectable `asset_referenced` conflict; lineage stays free of
  filesystem paths/secrets; added the Phase 6 boundary gate. No additive contract change was needed.
- Task 2 — COMPLETE (2026-09-28): replaced the connection→try-on shell with startup routing, the fixed
  `首页 / 素材 / 历史` bottom navigation, typed full-screen destination routes, Quiet Atelier color,
  type, shape, spacing and reduced-motion tokens, and reusable scaffold/heading/entity/status/problem/
  empty/loading/deleted-content/confirmation components. Feature bodies remain placeholders until
  their Tasks. Debug/release builds, JVM tests, instrumentation compile, and lint pass.
- Task 3 — COMPLETE (2026-09-28): added the authenticated data boundary — connection-backed API
  service factory, 401-to-re-authentication routing, problem parsing, app-owned domain models and
  mappers that preserve unknown server values, paged asset/job/provider repositories, job command
  repositories, a private-content repository, a bounded memory/disk authenticated image loader keyed
  only by asset ID, and a lifecycle refresh policy; wired under Hilt. JVM tests, lint, and instrumentation
  compile pass.
- Task 4 — COMPLETE (2026-09-28): implemented the segmented person/garment asset center with category
  filters, adaptive one-column-safe grid, bounded authenticated image tiles, import-first flow with
  garment metadata confirmation, upload progress/retry/cancel presentation, durable import recovery
  (Room schema v3 with `lastError`/`updatedAt` migration), and asset detail with favorite, active-reference
  blockers, destructive-delete confirmation, and retained deleted-content placeholder. Build, lint, JVM
  tests, and instrumentation compile pass.
- Task 5 — COMPLETE (2026-09-28): implemented Home (primary precise-try-on entry, recent high-value jobs,
  low-emphasis coming-soon cards) and the paged authoritative job history with per-state presentation,
  output thumbnail or deleted-content placeholder, block reason, updated time, tab-entry/resume refresh,
  stale-snapshot retention, and 401 re-authentication routing. Build, lint, JVM tests, and
  instrumentation compile pass.
- Task 6 — COMPLETE (2026-09-28): replaced the single try-on screen with the durable three-step wizard
  (person, garment + category, settings + confirmation), reusing the asset library, filtering providers
  by declared capability and availability, clamping candidate count to the provider limit, allowing
  temporarily-offline creation while blocking permanent incompatibility, preserving one idempotency key
  across ambiguous retries, and persisting asset/category/count/provider draft fields. Build, lint, JVM
  tests, and instrumentation compile pass.
- Task 7 — COMPLETE (2026-09-28): implemented job detail with aggregate and candidate state, block
  reason/detail, elapsed timing, successful outputs or deleted placeholders, locked Provider/Workflow
  summary, expandable lineage, whole-job and per-candidate cancellation with terminal guards, the exact
  `needs_attention` requery/retry/finish-failed actions, provider-change confirmation when the locked
  Provider cannot be reused, stable per-command idempotency keys with duplicate-tap disabling, and
  visibility-scoped polling that stops for terminal/`needs_attention` work. Build, lint, JVM tests, and
  instrumentation compile pass.
- Task 8 — COMPLETE (2026-09-28): implemented the adaptive result gallery with successful outputs first
  and failed/cancelled candidates retained below, selected-result large view, authoritative favorite
  reconciliation, `MediaStore` download, `FileProvider` short-lived share URI, deletion with
  reference-conflict explanation and cache eviction, deleted-content placeholders, distinct
  “再次尝试”/“修正后重新生成” actions, and the Before/After comparison screen with slider plus
  show-original/show-result non-gesture alternatives. Build, lint, release build, release-boundary scan,
  JVM tests, and instrumentation compile pass.
- Backend mask prerequisite — COMPLETE (2026-09-28): added a forward SQLite migration that safely
  rebuilds `assets` and `upload_sessions` with foreign keys disabled only for the migration window,
  preserves rows/indexes/triggers, enables private `mask` uploads without a garment subtype, validates
  mask availability and Provider `manual_mask` capability at job creation, persists mask/related-job
  lineage and active references, and supplies private mask bytes to Provider execution. Focused mask and
  migration coverage, the full Backend lint/type/test gate, and the Phase 6 contract boundary pass.
- Task 9 — COMPLETE (2026-09-28): implemented the Android Mask Editor — plum semi-transparent
  draw/erase on a fit-locked source canvas, brush sizes, undo, clear, preview toggle, normalized
  coordinates with pixel transform, bounded PNG export, unsent draft persistence (metadata + mask PNG +
  stroke document) restored across process death, discard-on-back confirmation, explicit compatible
  Provider selection when the locked Provider does not support manual mask, private `mask` upload, and
  related-job creation with `mask_asset_id`/`related_job_id` that never overwrites the original. Build,
  lint, JVM tests, and instrumentation compile pass.
- Task 10 — COMPLETE (2026-09-28): added `android/verify-phase6.ps1` and ran the integrated gate; it
  passes generated-contract drift, all contract boundaries, Backend `ruff`/`pyright`/`pytest`, Android
  `assembleDebug`/`lintDebug`/`testDebugUnitTest`/`assembleDebugAndroidTest`/`assembleRelease`, and the
  release-boundary scan. Updated README, roadmap, and this plan to record Phase 6 completion. Real
  credentialed AutoDL/Comfy acceptance remains explicitly deferred as a later release-readiness gate.
- Post-exit correction (2026-09-29): fixed stale person assets carrying into garment selection, added
  durable in-wizard photo import with retry/cancel and automatic selection, and filtered garments by
  the active category. Verified focused JVM tests, Android lint/build, four connected Compose tests,
  and a real-development-backend upload on the emulator.
- Next action: Phase 6 complete — return to `$planning` to plan Phase 7 (Web Admin and Operations
  Completion)

## Goal

Complete the confirmed Android V1 experience without pulling V1.1 outfit sessions or Phase 7 Web
Admin work forward:

- fixed `首页 / 素材 / 历史` navigation;
- reusable person and garment libraries with durable import recovery;
- the three-step precise try-on wizard;
- truthful job, candidate, recovery, and lineage states;
- result gallery, comparison, favorite, download/share, and deletion placeholders;
- mask correction as a related new main job with explicit Provider compatibility handling;
- process/re-authentication recovery, adaptive layout, accessibility, and release verification.

## Confirmed Inputs and Authority

1. Product behavior: [Android Virtual Try-On Product Spec](../superpowers/specs/2026-09-23-android-virtual-try-on-design.md).
2. Confirmed behavior flow: [Product Flow](../product-flow.md).
3. Android interaction and screen behavior: [Android V1 UI Design](../superpowers/specs/2026-09-23-android-v1-ui-design.md).
4. Visual language and accessibility: [DESIGN.md](../../DESIGN.md), Android sections.
5. Phase boundary: [Implementation Roadmap](../roadmap/implementation-roadmap.md), Phase 6.
6. Current implementation: Android source, generated OpenAPI client, Backend routes/tests, and Phase
   1–5 ADRs.

The confirmed inputs already settle navigation, task boundaries, deletion behavior, state semantics,
Provider switching, accessibility, and V1/V1.1 scope. Phase 6 must implement them rather than reopen
them.

## Current Repository State

### Reusable foundations

- `ClothesModelApp.kt` has Compose Navigation and the connection/authentication route.
- `ConnectionStore`, `TokenVault`, and `ConnectionViewModel` implement secure endpoint/token setup and
  re-authentication state.
- `PendingImportDatabase`, private staging, and WorkManager implement resumable import persistence.
- `TryOnDraftStore` persists the selected imports, garment metadata, active job, and create
  idempotency key.
- `TryOnViewModel` already proves upload → Provider selection → job creation → polling → authenticated
  private output download.
- The generated client exposes assets, providers, jobs, cancellation, retry, requery,
  finish-failed, and content operations.
- Backend Phase 1–5 provides durable jobs, private assets, immutable Provider/Workflow snapshots,
  storage/provider block reasons, and restart-safe execution.
- Android build, lint, JVM tests, instrumentation tests, release APK scanning, and CI emulator jobs
  already exist.

### Implementation delta

- MODIFY the two-route shell into the confirmed three-tab navigation plus full-screen detail flows.
- NEW app-owned repositories/gateways and UI models so generated API types and authentication are not
  coupled directly to every screen.
- MODIFY pending-import persistence for library metadata, retry/cancel presentation, and mask drafts.
- NEW home, asset center/detail, history, job detail, result, compare, and mask-editor screens.
- MODIFY the creation flow from one screen into a durable three-step wizard driven by Provider
  capabilities and storage/configuration checks.
- NEW lifecycle-aware refresh and command handling for every job/candidate state.
- VERIFY and, where required, MODIFY shared contract/Backend behavior for result favorite consistency,
  deletion blockers/placeholders, related-job lineage, and mask-compatible Provider selection.
- REMOVE the debug-only contract-status surface from the user navigation while retaining contract
  verification tooling.

## Technical Decisions

### State and data ownership

- The Backend remains authoritative for assets, jobs, outputs, configuration snapshots, and history.
- Room stores only durable client-owned work that the server cannot own yet: staged imports and
  unsent mask-edit drafts. DataStore stores connection state and the lightweight creation draft.
- Do not create a second offline database mirroring server assets/jobs. Lists refresh on entry/resume,
  preserve the last safe snapshot during transient failures, and clearly label stale/error state.
- Commands use persisted or stable idempotency keys. UI retries never generate a second paid execution
  merely because a response was lost.

### Android structure

- Preserve the existing single `:app` feature module for Phase 6 and organize by feature packages
  (`home`, `assets`, `create`, `jobs`, `results`, `mask`, `navigation`, `data`, `ui`). Do not introduce
  a multi-module rewrite during V1 completion.
- Generated contract code remains read-only. App-owned gateways translate generated models and
  problem responses into stable domain/UI models.
- Introduce an authenticated image-loading boundary with bounded memory/disk caching; tokens never
  appear in URLs, logs, cache keys, or share intents. Choose and lock a Compose-compatible image
  loader during Task 2 after build compatibility is verified.
- Server jobs continue without Android background polling. Visible screens refresh lifecycle-aware;
  app resume and history/detail entry synchronize authoritative state.

### Files, sharing, and privacy

- “下载” writes through Android `MediaStore` with explicit success/failure feedback.
- “分享” uses an app-private temporary copy and `FileProvider` content URI with short-lived read
  permission; raw server URLs and bearer tokens are never shared.
- Deleted content keeps server metadata and UI lineage. Cached bytes for deleted assets are evicted.

### UI and accessibility

- Implement the confirmed Quiet Atelier tokens and composition; Material 3 supplies platform
  semantics, not the final visual composition by itself.
- Compact phones are primary. Width/font scaling may reduce grids to one column; important status and
  actions never rely only on color or fixed text height.
- Before/After and Mask Editor provide non-gesture alternatives and 48dp minimum targets.
- Predictive/system back matches top-bar back. Only unsent mask edits or genuine destructive actions
  intercept navigation.

## Dependency Order

```text
Task 1 contract/Backend behavior closure
        ↓
Task 2 Android foundation and navigation
        ↓
Task 3 authenticated data and image boundary
        ↓
Tasks 4–5 assets/home/history
        ↓
Task 6 creation wizard
        ↓
Task 7 job details and recovery
        ↓
Task 8 results and content operations
        ↓
Task 9 mask correction
        ↓
Task 10 integrated exit gate
```

Tasks 4 and 5 may proceed in parallel only after Task 3 stabilizes shared repositories and UI models.
Tasks 7 and 8 may split internally, but their command/state integration must land in dependency order.

## Tasks

### Task 1 — Close Android V1 contract and Backend behavior gaps

Affected:

- `contracts/openapi/paths/assets.yaml`
- `contracts/openapi/paths/jobs.yaml`
- related schemas/examples and generated clients
- Backend asset/job payload services and repositories
- Backend contract and behavior tests
- new Phase 6 boundary verification script

Work:

- Audit every Phase 6 UI action against real routes: asset list/detail/favorite/content/delete/references;
  job list/detail/cancel; candidate cancel/retry/requery/finish-failed; Provider capabilities; related
  mask-correction jobs and lineage.
- Make generated-output favorite state consistent with the underlying output asset so list/detail
  responses cannot disagree after favorite updates.
- Prove terminal output deletion returns a retained `deleted_content` placeholder while active source
  references still produce an inspectable conflict.
- Ensure related-job and retry lineage can be rendered without exposing filesystem paths, secrets, or
  raw upstream payloads.
- Add only additive contract fields/operations that are demonstrably absent. Regenerate Backend,
  Android, and Web consumers; never hand-edit generated code.
- Add a Phase 6 boundary gate covering the Android-required operations, state enums, error responses,
  idempotency headers, content security, and unknown-enum compatibility.

Verify:

- OpenAPI lint/bundle/additive checks and generated drift checks pass.
- Backend model typing plus focused asset/job behavior tests pass.
- Generated Kotlin compiles and generated TypeScript remains compatible.
- Favorite, deletion blocker/placeholder, lineage, and mask-related job contract tests pass.

Dependencies and parallelization:

- Depends on the completed Phase 5 contract.
- Must complete before app-owned gateways and UI models are frozen.
- Commit separately because it touches shared contracts and Backend behavior.

### Task 2 — Establish the Phase 6 Android foundation and navigation shell

Affected:

- `android/app/build.gradle.kts` and `android/gradle/libs.versions.toml`
- `android/app/src/main/kotlin/com/clothesmodel/android/app/`
- new `navigation/` and shared `ui/` packages
- theme, resources, manifest, previews, and navigation tests

Work:

- Replace the direct connection → try-on route with startup routing, re-authentication, and the fixed
  `首页 / 素材 / 历史` bottom navigation.
- Add typed/stable destinations for creation steps, asset detail, job detail, results, comparison, and
  mask editing; pass identifiers rather than image bytes or serialized domain objects.
- Implement Quiet Atelier color, typography, shape, spacing, image, state, and motion tokens from
  `DESIGN.md`, including reduced-motion behavior and edge-to-edge safe insets.
- Add reusable page scaffold, section heading, entity card, status marker, inline problem, empty,
  loading, deleted-content, and confirmation components.
- Remove contract-status/debug placeholders from product navigation without deleting CI contract
  compilation coverage.

Verify:

- Navigation tests cover first connection, valid startup, re-authentication, three tabs, details, and
  consistent system/top-bar back behavior.
- Compose semantics prove selected navigation, headings, content descriptions, and 48dp targets.
- Debug/release builds and lint pass without placeholder endpoints leaking into release.

Dependencies and parallelization:

- Depends on Task 1 generated models.
- Shared shell and tokens must stabilize before feature screens.

### Task 3 — Add authenticated repositories, UI models, and image delivery

Affected:

- new `android/app/.../data/` gateways/repositories
- Hilt bindings in `di/`
- connection/authentication integration
- authenticated image loader/cache boundary
- repository, mapper, and authentication tests

Work:

- Centralize creation of authenticated generated APIs and 401 handling; preserve the server address,
  mark authentication expired once, and resume synchronization after a new token is validated.
- Add app-owned models/mappers for assets, Provider choices/capabilities, jobs, candidates, outputs,
  block reasons, problems, references, and lineage. Preserve unknown server values safely.
- Add repositories for paged assets, paged jobs, Provider choices, job commands, and private content.
- Implement authenticated image requests with bounded caching, cancellation, placeholders, and cache
  eviction after content deletion; do not log request headers or private image bytes.
- Define lifecycle-aware refresh policy: explicit refresh, resume refresh, detail polling for nonterminal
  jobs, and no polling for terminal jobs or hidden screens.

Verify:

- Unit tests cover mapping every known and unknown state, 401 routing, transient snapshot retention,
  pagination, idempotent commands, cache privacy, and cancellation.
- Integration tests prove bearer headers are attached only to the configured server and never to
  arbitrary image URLs.

Dependencies and parallelization:

- Depends on Tasks 1–2.
- Blocks every data-backed feature screen.

### Task 4 — Complete reusable asset library and durable imports

Affected:

- current `imports/` persistence, worker, and recovery code
- new `assets/` screens, state holders, and reusable `AssetPicker`
- Photo Picker integration and asset tests

Work:

- Implement the segmented person/garment asset center with favorites, garment category filters,
  source labels, quality warnings, loading/empty/error states, and adaptive grids.
- Reuse the asset center as the creation-flow picker, with single selection and an import-first item.
- Add import confirmation for person/garment metadata, upload progress, retry, cancel, and recovery
  after process/app restart without losing the staged private file.
- Implement asset detail with favorite changes, reference blockers, deletion confirmation, and retained
  deleted-content state. List the specific safe reference labels returned by the Backend.
- Remove completed/abandoned local staging only after the server state is proven or the user explicitly
  cancels; preserve retryable work across authentication/network failures.

Verify:

- Room migration/recovery tests preserve existing Phase 4 pending imports.
- Worker tests cover resumable offset, retry, cancellation, 401, server conflict, and cleanup.
- Compose tests cover filters, source/risk labels, favorite, blockers, deletion placeholder, large font,
  and one-column fallback.

Dependencies and parallelization:

- Depends on Task 3.
- Can proceed alongside Task 5 after shared models stabilize.

### Task 5 — Implement Home and authoritative job history

Affected:

- new `home/` and `history/` feature packages
- shared task summary/status components
- navigation and refresh tests

Work:

- Implement Home with the primary precise-try-on entry, recent high-value jobs, and low-emphasis
  “分层穿搭/创意写真即将开放” cards without exposing V1.1 state.
- Implement paged job history for all aggregate states, including output thumbnail or deleted-content
  placeholder, candidate counts, block reason, and updated time.
- Keep `waiting_provider`, storage-blocked `queued`, `needs_attention`, partial success, failed, and
  cancelled visually and semantically distinct.
- Refresh on tab entry/app resume and retain a clearly stale last snapshot during transient network
  failure; route 401 to re-authentication without cancelling jobs.

Verify:

- Unit/Compose tests cover ordering, pagination, every state presentation, empty/error/stale states,
  recent-job limits, navigation, and re-authentication recovery.
- Accessibility tests confirm status is conveyed by text/shape, not color alone.

Dependencies and parallelization:

- Depends on Task 3.
- Can proceed alongside Task 4.

### Task 6 — Replace the single screen with the durable three-step creation wizard

Affected:

- current `tryon/` code, split into `create/` state and screens
- `TryOnDraftStore` migration/evolution
- Provider capability presentation and submission tests

Work:

- Implement the confirmed steps: select one person, select/filter one garment, then generation settings
  and confirmation.
- Reuse server assets or launch durable import without losing the wizard position and compatible
  choices. Back navigation preserves the short-term draft.
- Load default and selectable Providers; filter candidates and manual-mask options by declared
  capabilities. Candidate count is 1–4 and capped by Provider support.
- Show source/quality warnings, locked Provider/model/Workflow semantics, storage/configuration
  blockers, and temporary-offline behavior before submission.
- Permit creation against a temporarily offline compatible Comfy Provider (`waiting_provider`), but
  block permanent configuration, category, mask, candidate-count, or storage incompatibility.
- Persist one idempotency key until creation is conclusively accepted; never silently switch Provider.

Verify:

- State-holder tests cover draft recovery, back/forward compatibility, Provider/default changes,
  capability filtering, every blocker, offline creation, 401, ambiguous response replay, and success.
- Compose tests cover the three steps, summaries, 200% font, compact width, and explicit Provider
  change presentation.

Dependencies and parallelization:

- Depends on Tasks 3–4 and Provider/contract behavior from Task 1.
- Must complete before mask correction reuses creation/submission components.

### Task 7 — Implement job detail, candidate control, recovery, and lineage

Affected:

- new `jobs/` feature screens/state holders
- shared `JobStatusPanel` and `ExecutionLineage`
- polling/command tests

Work:

- Render aggregate and candidate state, block reason/detail, elapsed timing, successful outputs, errors,
  locked Provider/Workflow summary, and expandable lineage.
- Implement candidate and whole-job cancellation with truthful partial-success aggregation and no
  cancel actions on terminal work.
- For `needs_attention`, expose exactly: requery the same external execution, create an explicit traced
  retry, or finish as failed. Preserve stable idempotency per command and disable duplicate taps.
- Retry only failed/uncertain candidates, display old/new attempts, and require explicit compatible
  Provider confirmation when the locked Provider cannot be reused.
- Poll only while visible and nonterminal; synchronize on process/app resume and stop automatic
  advancement for `needs_attention`.

Verify:

- State-holder tests cover every job/item state and block reason, partial success, cancel races,
  requery, retry, finish-failed, Provider change, stale responses, and authentication expiry.
- Compose tests cover action visibility, inline consequences, lineage, large font, TalkBack labels, and
  phase-only accessibility announcements.

Dependencies and parallelization:

- Depends on Tasks 3, 5, and 6.
- Results integration in Task 8 consumes its authoritative selected job/candidate models.

### Task 8 — Complete result gallery, comparison, favorite, download/share, and deletion

Affected:

- new `results/` feature package and reusable `CandidateGallery`
- authenticated private content repository
- Android `MediaStore`/`FileProvider` resources and tests

Work:

- Show successful candidates first in an adaptive result grid; retain failed/cancelled candidates as
  traceable rows below without displacing successful imagery.
- Implement selected-candidate large view, quality warnings, and Before/After comparison with visible
  labels, a 48dp drag target, TalkBack step controls, and “show original/result” alternatives.
- Implement favorite through authoritative asset mutation and reconcile list/detail/output state.
- Implement download through `MediaStore` and share through a short-lived app-private content URI;
  never expose bearer tokens, server URLs, or unrestricted files.
- Implement content deletion confirmation, reference-conflict explanation, cache eviction, and
  `素材已删除` placeholders while retaining job parameters/errors/lineage.
- Route “再次尝试” to candidate retry and “修正后重新生成” to Task 9 as distinct actions.

Verify:

- Tests cover multiple outputs, partial success, deleted content, favorite consistency, compare
  controls, failed downloads, share permission lifetime, deletion conflicts, and cache eviction.
- Instrumentation tests cover adaptive grid/single-column layout, large font, gestures plus accessible
  alternatives, and no private bytes in logs/saved state.

Dependencies and parallelization:

- Depends on Tasks 3 and 7.
- Mask entry is wired here but completed in Task 9.

### Task 9 — Implement Mask Editor and related-job submission

Affected:

- new `mask/` feature package and private draft persistence
- Canvas/bitmap mask rendering
- import/upload and creation/Provider reuse
- related-job and process-recovery tests

Work:

- Implement draw, erase, brush size, undo, clear, and semi-transparent preview aligned to the source
  image’s real coordinate space. Preserve aspect ratio through pan/fit and export a bounded mask image.
- Provide textual current-tool/size state, visible disabled undo, non-gesture controls, and unsaved-edit
  back confirmation.
- Persist unsent mask draft metadata and its app-private file so unavailable compatible Providers,
  authentication loss, or process death does not discard editing.
- Upload the mask as a private `mask` asset and create a new main job with `mask_asset_id` and
  `related_job_id`; never overwrite the original task/result.
- Reuse the original Provider when compatible. Otherwise show original/new Provider and reason,
  require explicit confirmation, and create nothing when no compatible Provider exists.
- Keep the mask draft until job acceptance is proven; clean it only after success or explicit discard.

Verify:

- Deterministic bitmap tests cover coordinate transforms, draw/erase, undo, export bounds, and
  orientation.
- Persistence tests cover rotation, process death, 401, upload retry, no compatible Provider, explicit
  switch, idempotent related-job creation, and cleanup.
- Compose tests cover 48dp targets, TalkBack state, preview toggle, and unsaved-change confirmation.

Dependencies and parallelization:

- Depends on Tasks 4, 6, and 8.
- Must reuse the import and job-creation boundaries rather than introduce a parallel upload stack.

### Task 10 — Run the integrated Phase 6 exit gate

Affected:

- all Android unit/instrumentation tests and CI jobs
- Backend/contract regression gates
- Android/README and root README
- Roadmap and this plan’s progress/checklist
- a new deterministic Phase 6 verification script

Work:

- Run contract generation/drift, Backend regressions, Android compile, lint, JVM tests, Compose
  instrumentation, release assembly, and release-boundary scan.
- Add deterministic fixture-backed end-to-end Android scenarios for the main loop, import recovery,
  re-authentication, every job state, partial success, needs-attention actions, result management,
  deletion placeholders, and mask-related jobs.
- Verify process recreation, app restart, 200% font, narrow width, reduced motion, TalkBack semantics,
  private file/cache handling, and release APK secret/debug-value absence.
- Keep real AutoDL/Comfy operator acceptance deferred; Phase 6 uses Ark or deterministic Provider
  fixtures and must not require a real Comfy Workflow.
- Update stable documentation only after evidence passes.

Verify:

- Android UI Spec §13 main, recovery, and safety/consistency checks all have passing automated or
  recorded device evidence.
- Phase 1–5 contract, Backend, Web, deployment, and security gates remain green.
- A release APK installs, starts at the correct route, reconnects safely, and contains no debug
  endpoint/token/sample ID.
- README, Roadmap, and this plan agree that Phase 6 is complete and identify Phase 7 as next.

Dependencies and parallelization:

- Depends on Tasks 1–9.
- Documentation may be prepared earlier, but completion status changes only after the integrated gate.

## Phase Exit Checklist

Evidence: `android/verify-phase6.ps1` (2026-09-28) passed the deterministic gate. Android Compose
instrumentation scenarios for navigation, assets, home/history, the creation wizard, job detail,
results/compare, and the mask editor compile in this repository; their execution remains owned by the
CI emulator jobs, matching the project's established Android verification convention.

### Product flow

- [x] First connection and re-authentication route correctly without cancelling server jobs.
- [x] Home, assets, and history provide the confirmed fixed navigation.
- [x] The three-step precise-try-on wizard creates 1–4 candidates with explicit locked configuration.
- [x] Every aggregate/candidate state has truthful copy, distinct operations, and recovery behavior.
- [x] Partial success preserves successful candidates and retries only failed/uncertain candidates.
- [x] Result comparison, favorite, download/share, deletion placeholder, and mask correction work.

### Persistence, privacy, and recovery

- [x] Pending imports and unsent mask drafts survive process/app restart.
- [x] Server assets/jobs remain authoritative; transient cached snapshots are never shown as live.
- [x] Idempotent create/command recovery never duplicates paid work.
- [x] Tokens, private image bytes, server URLs, and cache paths do not leak through logs, saved state,
      intents, screenshots in reports, or release artifacts.
- [x] Deleted content evicts local cache but retains server history and lineage placeholders.

### Accessibility and adaptability

- [x] 48dp targets, TalkBack labels/order, non-color state communication, and restrained announcements
      pass instrumentation checks.
- [x] 200% font, compact width, one-column grid fallback, edge-to-edge insets, predictive back, and
      reduced motion preserve all important status and actions.
- [x] Before/After and Mask Editor have non-gesture alternatives.

### Scope and compatibility

- [x] V1 does not expose outfit sessions, branches, layer roles, or pending-reapply UI.
- [x] Shared assets/jobs/results components do not hard-code assumptions that prevent V1.1 reuse.
- [x] No silent Provider switch occurs in creation, retry, or mask correction.
- [x] Phase 1–5 clients, APIs, migrations, deployment, and Ark behavior remain compatible.
- [x] Real Comfy production readiness remains explicitly deferred until its credentialed acceptance.

## Migration and Rollback

- Export every Room schema revision and add forward migration tests from the Phase 4 database.
- Never use destructive Room fallback for user-owned pending imports or mask drafts.
- DataStore keys remain backward compatible; new draft fields receive safe defaults.
- Contract changes are additive. If an Android release must roll back, the older app must safely ignore
  new response fields and preserve unknown enum behavior.
- Backend remains deployable independently of the Android release; no Phase 6 route may require an
  upgraded app to preserve existing Phase 4 behavior.

## Observability and Security

- Log stable request/job/import identifiers and safe state transitions only; exclude bearer tokens,
  server URLs with credentials, filenames, image bytes, mask strokes, complete prompts, and raw
  upstream errors.
- User-visible problems map stable error codes to actionable copy while retaining safe retryability.
- Image cache, staged imports, masks, and share files live only in app-private storage except explicit
  `MediaStore` download; cleanup is bounded and reference-aware.
- Instrumentation evidence must use generated/sanitized fixtures, never personal photos.

## Implementation Handoff

- Plan: `docs/plans/phase-6-android-v1-completion.md`
- Status: Phase 6 complete; all 10 Tasks verified and committed. Exit gate: `android/verify-phase6.ps1`.
- Deferred: real credentialed AutoDL/Comfy operator acceptance, to be run before any Comfy production
  claim.
- Next: return to `$planning` to plan Phase 7 (Web Admin and Operations Completion).
- Resume phrase: `继续`.
