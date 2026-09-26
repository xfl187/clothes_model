# Phase 2 Implementation Plan

## Goal

建立可信的数据、认证与私有资产平面，为后续任务、Provider、工作流和管理功能提供稳定基础：完成 SQLite 业务迁移、App/Admin 认证隔离、浏览器管理会话、主密钥加密设施、私有文件存储、可恢复上传、资产引用保护，以及 Android/Web 对这些边界的最小可运行集成。

本阶段只实现 Phase 2 所需能力，不实现正式任务执行、Provider 调用、工作流管理、成品生成、完整 Android 产品界面或完整 Web Admin 控制台。

## Progress

- Status: ACTIVE
- Tasks: 2 / 11 complete
- Task 1 — COMPLETE
- Task 2 — COMPLETE
- Tasks 3–11 — NOT STARTED
- Last verified: 2026-09-26
- Next: Task 3 — Establish token bootstrap, rotation foundation, and secret cryptography

## Confirmed Inputs

- `docs/roadmap/implementation-roadmap.md`
- `docs/plans/phase-1-engineering-baseline.md`
- `docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md`
- Product Flow documents under `docs/`
- Android UI Spec under `docs/`
- Web Admin UI Spec under `docs/`
- `DESIGN.md`
- Current repository and Phase 1 verification baseline

Authority order for behavioral questions:

1. Product Spec
2. Product Flow
3. Platform UI Specs
4. `DESIGN.md`
5. Confirmed Roadmap and phase plans
6. Current implementation

## Current State

- Phase 1 engineering baseline is complete and its exit checks pass.
- The repository is a monorepo with buildable Backend, Android, and Web Admin skeletons.
- Backend is a Python modular monolith using FastAPI, SQLAlchemy async, Alembic, and SQLite.
- The checked-in OpenAPI contract owns cross-client API types and generates Backend, Android, and Web artifacts.
- Backend currently has lifecycle/database infrastructure and stub Auth/Assets boundaries, but no Phase 2 business schema or production behavior.
- Android and Web can consume the contract/mock boundary but currently expose only engineering-skeleton surfaces.
- Deployment is a single Backend process with SQLite and local private storage; there is no Redis, worker cluster, or external object store.

## Implementation Delta

### New

- Phase 2 SQLite business tables and Alembic migrations.
- Token bootstrap/reset tooling, token verification, scoped authorization, browser admin sessions, CSRF defense, and login throttling.
- Master-key-backed authenticated encryption facility for future provider secrets.
- Private content-addressed local file storage and image normalization.
- Resumable upload sessions, idempotency records, capacity guard, and cleanup/recovery routines.
- Asset catalog persistence, favorite state, private content delivery, deletion placeholders, and reference protection.
- Android secure connection state, durable pending imports, and recoverable upload work.
- Web Admin login/session shell.
- Phase 2 integration, restart, migration, privacy, and security verification.

### Modify

- Additive OpenAPI resources and shared schemas required to complete Phase 2 behavior.
- Backend application composition, configuration, middleware, module wiring, and health diagnostics.
- Android navigation and dependency catalog for the minimal connection/import recovery surfaces.
- Web routing, API adapter, and session state for the minimal admin auth shell.
- CI and local verification commands to cover Phase 2 tests.

### Reuse

- Phase 1 monorepo layout, package boundaries, UoW/database lifecycle, problem-details error model, cursor pagination, idempotency header convention, generated-client workflow, lint/static-analysis baseline, and single-instance deployment decision.
- Existing API resources for App auth status, Admin session creation/deletion, uploads, assets, authenticated asset content, and admin storage status where they already express the required behavior.

### Explicitly Excluded

- Jobs, JobItems, scheduling, queue execution, and ComfyUI integration.
- Provider configuration CRUD, capability discovery, and live connectivity tests.
- Workflow version management and compatibility evaluation.
- Outfit lifecycle, generation history, retention execution, and output delivery.
- Full Android asset-library and try-on UI; only connection, re-authentication, import, and recovery paths required by Phase 2 are included.
- Full Web Admin dashboard and token-rotation UI; only login/session infrastructure is included.
- Multi-instance coordination, PostgreSQL, Redis, Kafka, Kubernetes, object storage, and distributed workers.

## Technical Decisions

### Persistence and transaction boundaries

- Continue with SQLite, SQLAlchemy async, and Alembic under the Phase 1 ADRs.
- Domain/application layers remain independent of FastAPI and SQLAlchemy. SQLAlchemy models and repositories stay in infrastructure packages and are exposed through ports/UoW boundaries.
- Use short write transactions and database uniqueness constraints for correctness. Do not hold a SQLite transaction open while streaming bytes or performing image decoding.
- Enable and verify SQLite foreign keys on every connection. Persist timestamps in UTC and expose RFC 3339 values at API boundaries.

### Phase 2 schema scope

The initial business schema will include only tables needed by this phase:

- access tokens and token lifecycle metadata;
- admin sessions and authentication-throttle/security-event state;
- idempotency records;
- stored objects and upload sessions;
- assets, person assets, garment assets, and asset references;
- security audit events containing metadata only.

Do not create job, provider, workflow, outfit, or output tables in this phase.

`asset_references` is an application-managed protection boundary with an asset foreign key plus source type, source identifier, optional display label, and active state. Future modules write references through a port; Phase 2 does not introduce polymorphic database foreign keys to tables that do not yet exist.

### Token model

- First-deploy tooling creates cryptographically random App and Admin tokens. A token contains a non-secret public identifier and a high-entropy secret so verification can select one record without scanning all hashes.
- Store only the public identifier, an Argon2id hash, scope, status, timestamps, and rotation lineage. Never store or log the full token.
- Use `argon2-cffi` `PasswordHasher` with parameters measured on the target host, stored in the encoded hash, and eligible for rehash on successful verification. The implementation must retain a bounded verification cost suitable for the single-instance deployment.
- The full token is shown once by the CLI. Admin token recovery is an operator/SSH reset flow. App token rotation is implemented as a backend application service and invalidation foundation; the full Admin rotation UI remains Phase 7.
- Scope checks are explicit: App credentials cannot call Admin resources, and an Admin session does not implicitly become an App credential.

### Admin browser sessions

- Admin Token login exchanges the token for a new high-entropy opaque session identifier.
- Store only a SHA-256 or keyed digest of the session identifier and CSRF value. Session secrets do not require a slow password hash because they are randomly generated, single-purpose bearer values.
- Send the session only in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie with an explicit lifetime and path. Local HTTP development uses an explicit development-only cookie policy; production configuration must refuse unsafe cookie settings.
- State-changing Admin requests require a separate CSRF header whose value is held in Web memory only and validated against the session, plus same-origin/Origin validation where the browser supplies it.
- Add a session inspection endpoint so Web can restore a cookie-backed session and obtain a fresh in-memory CSRF value without placing secrets in browser storage.
- Logout, expiry, Admin token reset, and explicit revocation invalidate sessions. Login throttling is SQLite-backed so it survives process restart and never stores attempted token values.

### Secret encryption boundary

- Add a generic envelope service using AES-256-GCM with a fresh 96-bit nonce for every encrypted value.
- Bind ciphertext to its purpose, record identifier, and encryption-format version with authenticated additional data.
- Load the master key through the existing secret-file configuration boundary. It must never be accepted from checked-in configuration, API requests, or logs.
- Store a versioned envelope containing only algorithm/version, nonce, and ciphertext. Fail closed on missing keys, wrong keys, invalid format, or authentication failure.
- This phase verifies the facility with test secrets; provider configuration persistence remains out of scope.

### Private FileStorage

- Implement a Backend-owned `FileStorage` port with a local-disk adapter. No upload or asset directory is mounted as public static content.
- Keep temporary uploads outside the immutable object namespace. Use confined server-generated paths only; user filenames are metadata and never become path components.
- Completion decodes supported JPEG/PNG images with Pillow, validates format and dimensions, normalizes orientation, strips EXIF/GPS metadata, serializes a normalized image, computes SHA-256 over stored bytes, fsyncs, and atomically renames it into a content-addressed object path.
- Use a `stored_objects` record for deduplication and reference counting. Delete physical content only when no durable content reference remains.
- Structural image validation in this phase covers decodability, type, byte limit, pixel/dimension limits, and orientation/metadata sanitation. Person visibility, garment occlusion, and other vision-quality judgments are not invented here.

### Resumable uploads and recovery

- Upload creation returns a server upload ID and offset zero. Append requires the expected offset and rejects mismatches without accepting ambiguous bytes.
- Serialize writes per upload in the single process. Persist only a confirmed offset after the corresponding file bytes are flushed. On restart, reconcile a temporary file to the database-confirmed offset by truncating uncommitted trailing bytes.
- Completion verifies declared size and optional client checksum, then normalizes/stores the image and creates the asset in one idempotent application workflow.
- Cancellation changes upload state before deleting temporary content; retries are safe. Expired abandoned sessions are cleaned by an in-process maintenance service owned by the single Backend instance.
- Idempotency is keyed by actor scope, operation, idempotency-key digest, and request digest. A reused key with a different request returns conflict; successful repeats return the original stable result. Raw idempotency keys are not persisted.

### Storage capacity guard

- Centralize a shared capacity policy that checks filesystem free space, configured reserve, requested write size, and bounded normalization overhead.
- Reject new upload sessions or unsafe writes with the shared problem-details model and HTTP 507 while preserving existing recoverable upload state.
- Expose authenticated storage status to Admin through the existing contract boundary.
- Define a reusable application port for future job admission, but do not implement job rejection or queued-job behavior before Phase 3.

### Asset behavior

- Persist a common Asset record plus exactly one PersonAsset or GarmentAsset subtype. Garments require the Product Spec category/source metadata supported by the current contract.
- Support cursor-based listing, detail, favorite updates, authenticated content delivery, reference inspection, and content deletion.
- Deletion removes private content only when no active references block it. A retained asset row becomes a deletion placeholder sufficient for future history/reference display; Phase 2 does not implement job or outfit history.
- Asset content responses require authentication, use safe download headers, do not expose filesystem paths, and do not expose content hashes as public identifiers.

### Android baseline

- Store non-secret connection state and authentication status in DataStore.
- Encrypt the App Token at rest with an Android Keystore-backed AES-GCM key; do not place it in resources, BuildConfig, logs, Room, DataStore plaintext, or backups.
- Enforce HTTPS in release builds. Permit only explicit emulator/local development exceptions in debug configuration.
- On App-token 401, retain the server URL, clear authenticated state, pause dependent upload work, and route to re-authentication without an infinite retry loop.
- Use Room for pending-import/upload records and schema migrations. Copy a selected image into app-private staging before durable work begins so process death or URI-permission loss does not require gallery reselection.
- Use unique WorkManager work for recoverable uploads with network constraints, bounded backoff, server-offset reconciliation, explicit cancellation, and server cleanup.
- Implement only the minimum S01/S02/S03 connection/re-authentication and import-recovery surfaces needed to prove this phase. Full asset-library UX remains Phase 6.

### Web Admin baseline

- Add `/login`, a session context/gateway, and protected-route guard.
- Send cookie credentials on Admin API calls. Keep CSRF state in memory only and refresh it through session inspection after navigation/reload.
- Distinguish invalid credentials, throttling, session expiry, and server/network unavailability using the shared problem-details model.
- Preserve the intended internal target route across session-expiry redirect, after validating it as a same-origin application path.
- Store neither Admin Token nor Admin session/CSRF secrets in localStorage or sessionStorage.
- Do not implement production A01–A12 pages in this phase.

### Dependency and version handling

- Backend may add compatible stable releases of `argon2-cffi`, `cryptography`, and Pillow and must lock them through the existing dependency workflow.
- Android may add compatible stable AndroidX DataStore, Security/Keystore support, Room, WorkManager, and lifecycle/navigation test dependencies through the version catalog. Exact versions are selected and locked during their owning task after confirming compatibility with the repository's Kotlin, AGP, compile SDK, and KSP/KAPT baseline.
- Web should use the existing React/Vite/TypeScript stack and existing request/test infrastructure; add only small focused dependencies when the platform APIs or current stack cannot safely provide the required behavior.
- A dependency-version adjustment for toolchain compatibility is an implementation detail if it does not change these architecture or product decisions; record the reason in the task result.

## ADRs

Create these long-lived decision records in Task 1:

### ADR-0006 — Token, browser session, and secret protection

Record:

- token public-ID plus Argon2id-secret verification model;
- App/Admin scope isolation and rotation/reset boundaries;
- opaque browser session and CSRF model;
- SQLite-backed throttle/revocation behavior under the single-instance constraint;
- AES-256-GCM master-key envelope and secret-file injection boundary;
- alternatives rejected, including plaintext/reversible token storage, JWT browser sessions, browser storage for Admin secrets, and per-provider ad hoc encryption.

### ADR-0007 — Private local content-addressed storage

Record:

- Backend-owned private local disk storage;
- normalized-image hash as the immutable object identity;
- atomic temp-to-object lifecycle, deduplication, and database/file reconciliation;
- authenticated streaming rather than public static serving;
- asset deletion/reference behavior and single-instance maintenance ownership;
- alternatives rejected, including public upload directories, original-file passthrough, database blobs, and premature external object storage.

Do not create ADRs for ordinary library-version choices or individual test tools.

## Target Repository Structure

Exact filenames may be adapted to established repository naming, but responsibilities must land in these boundaries:

```text
.
├─ apps/
│  ├─ backend/
│  │  ├─ migrations/                 # Phase 2 business migration(s)
│  │  ├─ src/
│  │  │  ├─ app/                     # composition, middleware, maintenance startup
│  │  │  ├─ config/                  # auth/storage/master-key settings
│  │  │  ├─ security/                # hashing, sessions, CSRF, encryption, audit
│  │  │  ├─ storage/                 # FileStorage adapter, capacity, reconciliation
│  │  │  ├─ auth/                    # domain/application/http/infrastructure
│  │  │  └─ assets/                  # domain/application/http/infrastructure
│  │  ├─ tests/
│  │  │  ├─ unit/
│  │  │  ├─ integration/
│  │  │  ├─ contract/
│  │  │  └─ security/
│  │  └─ tools/                      # operator bootstrap/reset entry points
│  ├─ android/
│  │  └─ app/src/
│  │     ├─ main/.../connection/     # server/auth state and API wiring
│  │     ├─ main/.../imports/        # Room, staging, WorkManager upload
│  │     ├─ main/.../security/       # Keystore-backed token store
│  │     ├─ test/
│  │     └─ androidTest/
│  └─ web-admin/
│     └─ src/
│        ├─ features/auth/            # login/session/route guard
│        ├─ api/                      # cookie + CSRF adapter
│        └─ test/
├─ contracts/
│  ├─ openapi/                        # Phase 2 additive API/schema changes
│  └─ generated/                      # all three generated clients/artifacts
├─ docs/
│  ├─ adr/                            # ADR-0006 and ADR-0007
│  └─ plans/
│     └─ phase-2-trusted-data-auth-asset-plane.md
└─ scripts/                            # existing contract/build/verification entry points
```

## Contract and Integration Strategy

The checked-in OpenAPI document remains the cross-platform contract owner. Task 1 closes only Phase 2 gaps, regenerates all consumers, and prevents Backend, Android, and Web from inventing local variants.

### Existing resources to retain

- App authentication status.
- Admin session creation and deletion.
- Upload create, status, append, cancel, and complete.
- Asset list, detail, and authenticated content.
- Admin storage status.

### Additive Phase 2 contract gaps

- Admin session inspection/refresh response containing session state, expiry, and a CSRF value suitable for memory-only use.
- Asset favorite/metadata update request and response.
- Asset deletion/content-removal operation with explicit placeholder outcome.
- Asset-reference list resource with cursor pagination and blocker metadata.
- Any missing upload cancellation/completion outcomes needed for deterministic retry and recovery.

### Shared conventions

- Authentication:
  - App endpoints use the existing App bearer scheme.
  - Admin endpoints use the Admin session cookie; login alone accepts the Admin Token input.
  - State-changing Admin requests also require the CSRF header.
- Errors: continue using the shared RFC 9457-style problem-details envelope and stable application error codes. Phase 2 must cover unauthenticated, wrong scope, invalid credentials, throttled, CSRF rejected, offset conflict, idempotency conflict, invalid image, referenced asset, storage insufficient, and resource missing.
- Pagination: retain opaque cursor pagination and stable deterministic ordering; no offset pagination.
- Idempotency: retain the existing header convention for upload creation/completion and document its actor/operation/request binding. Do not mark streaming append idempotent; it is guarded by expected offset.
- Versions: resource versions/ETags, where present, are server-issued opaque values. Do not reuse content hash as a public concurrency or resource version.
- Capabilities: no new Provider capability model is implemented in Phase 2; existing shared capability representation remains unchanged.
- Compatibility: contract changes are additive within `/api/v1`. Generated artifacts for Backend, Android, and Web are committed and checked for drift.
- Contract server: mock/contract fixtures represent success and all Phase 2 boundary errors so Android and Web tests do not require future business modules.

## Tasks

### Task 1 — Close Phase 2 contracts and record ADRs

Affected:

- `contracts/openapi/`
- generated Backend, Android, and Web contract artifacts
- contract fixtures/mock server data
- `docs/adr/`
- contract validation and drift tests

Work:

- Compare the current OpenAPI paths/schemas with the Phase 2 contract gaps listed above and make only additive `/api/v1` changes.
- Define the Admin session inspection/CSRF response, asset update/delete/reference resources, and any missing deterministic upload outcomes.
- Add Phase 2 problem codes and security requirements without duplicating platform-local enums.
- Document authentication, CSRF, pagination, idempotency, opaque-version, and error semantics in the contract descriptions.
- Create ADR-0006 and ADR-0007 with the decisions and rejected alternatives specified by this plan.
- Regenerate all three consumer artifacts and update mock fixtures before any runtime implementation begins.

Dependencies:

- Phase 1 complete.
- Blocks Tasks 2–11 because persistence, Backend handlers, and clients must implement one shared boundary.

Verify:

- OpenAPI lint, bundle, semantic validation, and breaking-change checks pass.
- Generated artifacts are clean and reproducible for Backend, Android, and Web.
- Contract tests prove every Phase 2 route has its intended security requirement and declared problem responses.
- Mock server exercises success, invalid credentials, wrong scope, CSRF failure, offset conflict, idempotency conflict, referenced asset, and storage-insufficient responses.
- ADR links and status are valid.

### Task 2 — Add the Phase 2 business schema and persistence adapters

Affected:

- Backend Alembic migrations and SQLAlchemy metadata
- Backend auth/assets/security/storage infrastructure packages
- repository and UoW tests

Work:

- Add the Phase 2 tables defined in the schema-scope decision, with foreign keys, checks, uniqueness constraints, indexes, lifecycle timestamps, and explicit state fields.
- Model exactly-one asset subtype invariants at the strongest practical database/application boundary.
- Add repository ports and SQLAlchemy adapters for tokens, sessions, throttle state, idempotency, uploads, stored objects, assets, references, and security audit metadata.
- Extend the existing UoW rather than introducing independent transaction managers per module.
- Define deletion/cascade rules so asset reference blockers and shared stored objects cannot be accidentally removed.
- Make migration upgrade safe both from an empty database and from the Phase 1 baseline; provide and test downgrade for the new revision.

Dependencies:

- Task 1 contract and ADR decisions.
- Blocks Tasks 3–7 and integration verification.

Verify:

- Alembic upgrades an empty database to head and upgrades a Phase 1 database to head.
- Downgrade and re-upgrade succeed for the Phase 2 revision in disposable databases.
- Foreign-key enforcement, unique constraints, lifecycle checks, reference protection, and shared-object behavior have integration tests.
- Repository/UoW tests prove commit, rollback, and conflict translation under concurrent duplicate attempts.
- No future-phase business tables appear in the migration.

### Task 3 — Establish token bootstrap, rotation foundation, and secret cryptography

Affected:

- Backend security and auth domain/application/infrastructure packages
- Backend operator CLI/tool entry points
- Backend configuration and environment template
- Backend unit, integration, and security tests

Work:

- Add compatible locked Backend dependencies for Argon2id hashing and AES-GCM authenticated encryption.
- Implement App/Admin token generation, parsing, slow-hash verification, scope/status checks, rehash-on-success support, and safe redaction.
- Implement an idempotent first-deploy CLI that creates missing App/Admin tokens and displays each full value exactly once.
- Implement operator-only Admin token reset and the backend App token rotate/revoke application-service foundation without adding the Phase 7 UI.
- Implement the versioned master-key encryption facility with purpose/record-bound AAD and secret-file loading.
- Add metadata-only security audit events for bootstrap, reset, rotate, revoke, and cryptographic failures; never record presented credentials or plaintext secrets.

Dependencies:

- Task 2 persistence.
- Blocks Task 4 and all authenticated integration work.

Verify:

- Generated tokens have the specified entropy/format and only hashes plus public metadata reach SQLite.
- Correct token/scope verifies; malformed, wrong, revoked, expired, and cross-scope credentials fail without leaking distinctions useful to an attacker.
- Repeated bootstrap does not replace existing active tokens or redisplay secrets.
- Admin reset invalidates the intended credential/session lineage and emits safe audit metadata.
- AES-GCM round-trip succeeds; wrong key, modified nonce/ciphertext/AAD, missing key, and unknown envelope version fail closed.
- Captured CLI output, logs, exceptions, database rows, and test reports contain no token, master key, or plaintext test secret beyond the one explicitly asserted bootstrap display.

### Task 4 — Enforce auth scopes and Admin browser sessions

Affected:

- Backend auth application/http/infrastructure packages
- Backend middleware and route composition
- Admin session contract handlers
- Backend auth, cookie, CSRF, throttle, and authorization tests

Work:

- Implement App bearer authentication and explicit App/Admin authorization dependencies.
- Ensure authentication/authorization occurs before existing stub handlers so protected future boundaries cannot leak through unguarded placeholders.
- Implement Admin session create, inspect/CSRF refresh, and delete using opaque cookie sessions.
- Apply production cookie attributes, explicit expiry/revocation, Origin checks, and CSRF validation for state-changing Admin requests.
- Implement SQLite-backed, bounded login throttling with safe keying and recovery windows.
- Map auth failures to stable shared problem codes while avoiding credential-oracle detail.
- Ensure App token invalidation requires re-authentication but does not imply cancellation of server work; jobs are not implemented here.

Dependencies:

- Tasks 1–3.
- Blocks authenticated storage/assets and both client shells.

Verify:

- App Token succeeds on App routes and cannot call any Admin route.
- Admin session succeeds on Admin routes and is not accepted as an App bearer credential.
- Login cookie attributes, lifetime, logout, expiry, reset invalidation, and session inspection behave as contracted.
- Missing/incorrect CSRF, hostile Origin, session fixation attempts, replay after logout, and throttled login are rejected.
- HTTP tests cover 401, 403, 429, and safe problem bodies without tokens or internal hashes.
- Production startup rejects unsafe cookie configuration; explicit local development mode remains usable.

### Task 5 — Implement private local FileStorage and image normalization

Affected:

- Backend storage infrastructure and ports
- Backend assets application boundary
- Backend storage configuration
- Backend file/image/security tests and fixtures

Work:

- Add the locked Pillow dependency and implement the private local-disk `FileStorage` adapter.
- Implement confined server-generated temp/object paths, safe open behavior, fsync, atomic rename, streaming read, and deletion.
- Decode JPEG/PNG, enforce byte/pixel/dimension limits, normalize EXIF orientation, strip all EXIF/GPS data, serialize normalized content, and hash stored bytes.
- Implement content-addressed object placement, stored-object deduplication, and cleanup rules that respect durable references.
- Add restart reconciliation helpers for abandoned temp files and database/file mismatches; do not silently delete ambiguous durable data.
- Keep all content unavailable through public static routes.

Dependencies:

- Task 2 schema; Task 3 configuration encryption boundary where shared secret loading utilities are reused.
- Blocks Tasks 6–7 and Android end-to-end imports.

Verify:

- Valid JPEG/PNG fixtures normalize and round-trip with correct MIME/dimensions.
- Orientation is visually/dimensionally normalized and EXIF/GPS metadata is absent from stored bytes.
- Corrupt, unsupported, oversized, decompression-bomb, invalid-dimension, traversal, and symlink-escape cases are rejected safely.
- Identical normalized content deduplicates without losing independent asset references.
- Interrupted temp writes do not become immutable objects; atomic replacement and reconciliation tests pass on supported development/CI filesystems.
- No route or deployment configuration exposes the storage root publicly.

### Task 6 — Implement capacity, idempotency, and resumable uploads

Affected:

- Backend assets/upload application and HTTP packages
- Backend storage capacity and maintenance services
- Backend idempotency infrastructure
- upload contract/integration/restart tests

Work:

- Implement upload create, status, append, cancel, and complete according to the checked-in contract.
- Enforce expected offset, declared limits, per-upload serialization, confirmed-offset persistence, restart truncation, and explicit upload state transitions.
- Implement request-bound idempotency for create and complete, including stable replay and mismatch conflict.
- On completion, verify size/checksum, invoke image normalization/storage, and create exactly one asset result.
- Implement cancellation and expiry cleanup so server temp content is removed without deleting completed durable objects.
- Apply the shared storage-capacity policy before new sessions and writes, return 507 when unsafe, preserve recoverable state, and expose Admin storage status.
- Start the cleanup/reconciliation service only in the single Backend process and make repeated cleanup safe.

Dependencies:

- Tasks 1–5.
- Blocks Tasks 7, 9, and Phase 2 end-to-end verification.

Verify:

- Create/append/status/complete works across multiple chunks and returns the contracted offsets/states.
- Wrong offsets, oversize chunks, checksum mismatch, invalid image, and invalid state transitions do not corrupt confirmed data.
- Same idempotency key/request replays the same result; a changed request returns the contracted conflict; concurrent duplicates create one result.
- Forced process interruption followed by restart reconciles trailing bytes and resumes at the confirmed offset.
- Cancel and expiry remove temporary data and are safe to repeat.
- Simulated low capacity rejects new/unsafe writes with 507, preserves resumable sessions, and reports safe Admin diagnostics.

### Task 7 — Implement the asset catalog, private content, and reference protection

Affected:

- Backend assets domain/application/http/infrastructure packages
- asset and reference contract handlers
- Backend asset authorization, pagination, deletion, and content tests

Work:

- Implement PersonAsset and GarmentAsset creation from completed uploads with required subtype/category/source metadata.
- Implement opaque-cursor asset listing with deterministic ordering, type filters supported by the contract, detail, and favorite updates.
- Stream asset content only through authenticated handlers with safe content headers and no path/hash disclosure.
- Implement reference listing and the generic future-module reference registration/release port.
- Implement deletion semantics: return blockers for active references, otherwise remove content association, leave the specified placeholder, and delete physical stored content only when the last durable reference is gone.
- Keep future job/outfit/history behavior behind the generic reference boundary; use fixtures to prove blockers without implementing those modules.

Dependencies:

- Tasks 1–6.
- Blocks Android asset import completion and Phase 2 integration.

Verify:

- App-authenticated list/detail/favorite/content operations match the contract; unauthenticated and Admin-cookie-only requests fail.
- Cursor traversal has no duplicates or omissions under a stable dataset and rejects malformed cursors safely.
- Content is never reachable by a static or guessed filesystem URL.
- Active references return the contracted blocker response and leave bytes/metadata intact.
- Unreferenced deletion produces the contracted placeholder and removes bytes only after the last object reference.
- Two assets sharing one stored object can be deleted independently without premature physical deletion.

### Task 8 — Implement Android trusted connection and authentication recovery

Affected:

- Android version catalog and app Gradle configuration
- Android connection, security, networking, state, navigation, and minimal UI packages
- Android unit and instrumentation tests

Work:

- Select compatible stable DataStore, Keystore/security support, lifecycle/navigation, and test dependencies and lock them in the version catalog.
- Implement server URL validation/normalization and the generated-client API factory.
- Persist non-secret connection state with DataStore and encrypt the App Token with an Android Keystore-backed key.
- Enforce release HTTPS policy and explicit debug-only emulator/local exceptions.
- Implement initial connection verification, authenticated startup restoration, and 401 recovery that retains the URL, clears authenticated state, pauses dependent work, and navigates to re-authentication.
- Build the minimum connection/re-authentication UI states from S01/S02/S03 required to exercise these behaviors; do not expand into the Phase 6 product UI.
- Apply log/network redaction and exclude sensitive state from backups where applicable.

Dependencies:

- Tasks 1 and 4; may proceed in parallel with Tasks 5–7 once the auth contract is stable.
- Blocks Task 9 and Android end-to-end verification.

Verify:

- Unit tests cover URL normalization, invalid URLs, error classification, and auth-state transitions.
- Instrumentation tests prove token ciphertext rather than plaintext is persisted, the Keystore key is non-exported through application APIs, and process recreation restores connection state.
- Valid App Token connects; invalid/revoked token retains the URL and requires re-authentication without an infinite retry.
- Release configuration rejects HTTP and contains no debug server/token values; approved debug local endpoints work.
- Logs, crash-visible errors, preferences/DataStore inspection, and backup configuration expose no App Token.

### Task 9 — Implement Android pending import and upload recovery

Affected:

- Android Room database and migrations
- Android import staging, repository, WorkManager, and minimal recovery UI packages
- Android unit, integration, and instrumentation tests

Work:

- Select compatible stable Room, WorkManager, and compiler/plugin versions and lock them.
- Add Room entities for pending imports and confirmed upload progress with explicit schema version/migration tests.
- Copy user-selected content into app-private staging before creating durable work; store display metadata but not dependent transient content URIs.
- Implement unique WorkManager upload work using the generated client, network constraints, bounded backoff, server status/offset reconciliation, and durable progress.
- Send person/garment metadata through the contracted completion path and reconcile the resulting Asset exactly once.
- Implement retry, explicit cancel with server cancellation/acknowledgment, local cleanup, restart recovery, and 401 pause/resume after re-authentication.
- Build only the minimum import-progress/recovery surface necessary to prove Product Flow semantics.

Dependencies:

- Tasks 6–8.
- Blocks Android integration portion of Task 11.

Verify:

- Import survives activity/process/app restart without requiring gallery reselection.
- Network interruption resumes from the server-confirmed offset and does not duplicate chunks or assets.
- Unique work prevents parallel duplicate uploads for one import.
- Retry preserves local selection/staging; cancellation removes server temp data after acknowledgment and then cleans local staging/state.
- Revoked App Token pauses work, retains recoverable import state, and resumes after successful re-authentication.
- Room migration, worker retry/backoff, staging cleanup, and no-token-in-logs tests pass.

### Task 10 — Implement the Web Admin auth/session shell

Affected:

- Web Admin auth feature, API adapter, router, and minimal login UI
- Web unit/component/browser tests
- Web mock/contract fixtures

Work:

- Implement `/login` from the confirmed A00 behavior using the generated Admin session API.
- Add a session provider/gateway and protected-route guard that inspect the cookie-backed session at startup and retain CSRF only in memory.
- Send credentials and CSRF correctly, implement logout, and handle session expiry by redirecting to login while preserving a validated internal target.
- Distinguish invalid Admin Token, throttling, offline/unreachable server, and expired session using contracted errors.
- Ensure Admin Token is used only for the login request and is cleared from component memory as soon as practical.
- Add a minimal protected placeholder route only to prove guarding; do not implement the Phase 7 Admin pages.

Dependencies:

- Tasks 1 and 4; may proceed independently of asset implementation.
- Blocks Web integration portion of Task 11.

Verify:

- Unit/component tests cover login states, safe error messages, guard bootstrap, logout, expiry redirect, and safe target restoration.
- Browser tests against the real Backend prove cookie session restoration and memory-only CSRF refresh after reload.
- State-changing requests fail without valid CSRF and succeed with the session-issued value.
- Browser storage and production bundles contain no Admin Token, session ID, CSRF fixture, or debug credential.
- The protected placeholder cannot be loaded with App Token or without an Admin session.

### Task 11 — Run the Phase 2 integration and security exit gate

Affected:

- Phase 2 integration/security suites across Backend, Android, and Web
- CI workflows and verification scripts
- environment template and deployment/operator documentation
- this plan's progress and exit checklist

Work:

- Add a deterministic Phase 2 verification entry point that composes contract, migration, Backend, Android, Web, and security checks.
- Exercise a fresh single-instance deployment: configure secret files/storage, migrate, initialize tokens, start Backend, authenticate both clients, import an asset, restart, resume/retrieve it, and verify Admin session behavior.
- Add negative cross-scope, public-file, CSRF, traversal, malformed-image, upload-replay, low-capacity, restart, cancellation, reference-blocker, and log-redaction scenarios.
- Verify environment templates document non-secret settings and secret-file names only; document backup/restore implications for SQLite, storage root, and master key without implementing a new backup product.
- Update CI to run practical deterministic checks on every change and keep heavier Android/browser/security scenarios as explicit jobs if required by runtime cost.
- Mark Tasks 1–11 and the exit checklist complete only from fresh verification evidence.

Dependencies:

- Tasks 1–10 complete.

Verify:

- The Phase 2 verification command passes from a clean checkout with documented prerequisites.
- CI runs the intended contract/build/lint/static-analysis/unit/integration/security matrix.
- Fresh migration/bootstrap and restart/recovery scenarios pass without manual database or filesystem edits.
- A redaction scan of logs, generated reports, databases, browser storage, Android persisted state, and build artifacts finds no plaintext credentials, master keys, provider-like test secrets, or image bodies.
- Every Phase Exit Checklist item below is backed by an automated check or a documented operator verification with captured result.

## Phase Exit Checklist

### Contract and architecture

- [ ] Phase 2 OpenAPI additions are additive, linted, bundled, validated, and generated for all three consumers.
- [ ] Shared auth, error, cursor, idempotency, version, upload, asset-reference, and storage semantics are documented once and consumed consistently.
- [ ] ADR-0006 and ADR-0007 are accepted and linked from relevant code/documentation.
- [ ] No Phase 3–9 business modules or tables were implemented.

### Database and migration

- [ ] Empty SQLite database upgrades to head deterministically.
- [ ] Phase 1 database upgrades to Phase 2 head and the Phase 2 revision downgrade/re-upgrade test passes.
- [ ] Foreign keys, checks, uniqueness, indexes, UTC timestamps, and delete rules are verified.
- [ ] Backend restart preserves tokens, sessions as intended, uploads, assets, references, and stored-object consistency.

### Authentication and secrets

- [ ] First-deploy tooling creates high-entropy App/Admin tokens and displays full values once only.
- [ ] SQLite contains slow hashes and safe metadata, never full App/Admin tokens.
- [ ] App Token cannot call Admin APIs; Admin cookie cannot substitute for App bearer auth.
- [ ] Revoked/rotated App Token forces Android re-authentication while retaining server URL and recoverable import state.
- [ ] Admin login produces a bounded Secure/HttpOnly/SameSite cookie session; logout, expiry, reset, and revocation work.
- [ ] State-changing Admin APIs enforce CSRF and same-origin protections.
- [ ] Login throttling survives restart and does not persist attempted secrets.
- [ ] AES-256-GCM master-key facility passes round-trip and tamper/wrong-key failure tests.
- [ ] Tokens, session secrets, CSRF values, master keys, plaintext encrypted test secrets, request bodies, and image bodies are absent from logs.

### Storage, uploads, and assets

- [ ] All uploaded/stored images remain private and are served only through authenticated API handlers.
- [ ] JPEG/PNG validation, orientation normalization, EXIF/GPS stripping, limits, and safe serialization pass.
- [ ] Atomic content-addressed storage and deduplication work without premature deletion.
- [ ] Resumable upload supports retry, confirmed offset, restart recovery, and deterministic idempotent completion.
- [ ] Cancel and expiry remove server temporary content and are safe to repeat.
- [ ] Insufficient capacity blocks new/unsafe writes with the contracted response while preserving recoverable state.
- [ ] Asset list/detail/favorite/content behavior conforms to the contract.
- [ ] Active references block content deletion with inspectable blocker metadata.
- [ ] Unreferenced deletion leaves the contracted placeholder and releases physical content only after the last reference.

### Android

- [ ] Android clean build, lint/static analysis, unit tests, and required instrumentation tests pass.
- [ ] Server URL/auth state restores after process restart; App Token is encrypted with an Android Keystore-backed key.
- [ ] Release builds enforce HTTPS and contain no debug credentials or permissive network policy.
- [ ] Invalidated App Token retains the server URL and returns to re-authentication without an infinite retry.
- [ ] Pending import persists in Room and app-private staging across activity/process/app restart.
- [ ] Network interruption resumes from server-confirmed offset without duplicate asset creation.
- [ ] Retry and cancel match Product Flow; cancel removes server temp and then local pending state.

### Web Admin

- [ ] Web Admin clean build, lint/static analysis, unit/component tests, and browser auth tests pass.
- [ ] Admin login distinguishes invalid credentials, throttle, offline/unreachable, and session expiry.
- [ ] Cookie session restores after reload and CSRF state is refreshed into memory only.
- [ ] Logout and expiry route to login and safely restore the intended internal destination.
- [ ] Admin Token, session ID, and CSRF value are absent from localStorage/sessionStorage and production bundles.

### Integration and operations

- [ ] Fresh single-instance local deployment can migrate, initialize tokens, start, authenticate, import, restart, resume, and retrieve a private asset.
- [ ] Backend, Android, and Web consume the same checked-in/generated contract without drift.
- [ ] CI covers contract validation, migrations, builds, lint/static analysis, tests, and deterministic security checks.
- [ ] Environment template documents all non-secret Phase 2 settings and secret-file boundaries without example production secrets.
- [ ] Operator documentation covers bootstrap, Admin reset, App rotation foundation, storage paths, master-key preservation, restart reconciliation, and safe diagnostics.
- [ ] V1 single-instance ownership of maintenance, upload serialization, SQLite, and local storage remains explicit and enforced.

## Risks

- Argon2id settings that are too expensive can starve a small single-instance server; benchmark on the target class of hardware, cap concurrent verification, retain encoded parameters, and support rehashing.
- Database and filesystem operations cannot share one atomic transaction. Use explicit state transitions, immutable content-addressed objects, atomic renames, idempotency, and restart reconciliation rather than pretending they are globally atomic.
- SQLite write contention can appear during concurrent login, upload, and cleanup activity. Keep transactions short, use constraints as the final arbiter, serialize only per-upload work, and make cleanup bounded.
- Image decoding is an attacker-controlled boundary. Enforce byte/pixel limits before expensive work, treat decompression warnings as failures, isolate paths, and maintain adversarial fixtures.
- Android content URIs may lose permission after process death. Copy into app-private staging before scheduling durable work, then apply bounded retention/cleanup so staging does not grow indefinitely.
- WorkManager/Room/DataStore versions must remain compatible with the current Kotlin/AGP/compile-SDK toolchain. Select current compatible stable versions during Tasks 8–9, lock them, and record any toolchain-mandated adjustment.
- Secure cookies complicate HTTP localhost development. Keep a deliberately explicit development-only mode and verify production refuses it.
- Contract additions can cause generated-client churn. Complete Task 1 first and require generation drift checks before runtime work.
- Content deduplication must not become an information leak. Keep hashes and object identities internal, require auth for content, and expose asset IDs only.
- Losing the master key makes encrypted future secrets unrecoverable. Treat it as deployment state, document preservation/restore, and fail closed; do not add insecure recovery copies.

## Upstream Conflicts

None identified.

The following are phase-boundary clarifications, not Product/UI changes:

- Phase 2 implements only the minimal Android connection, re-authentication, import, and recovery surfaces needed to prove Product Flow. The complete Android asset-library and try-on experience remains Phase 6.
- Phase 2 implements the backend App-token rotation/reset foundation, not the complete Web Admin token-management UI assigned to Phase 7.
- Phase 2 exposes a reusable storage-admission boundary, but job admission/queue behavior begins in Phase 3.
- Phase 2 performs structural image safety/normalization checks only. It does not invent unconfirmed person/garment vision-quality rules.

If implementation evidence contradicts Product Spec, Product Flow, or a UI Spec, stop the affected task and record `Upstream Conflict` rather than silently changing those inputs.

## Implementation Handoff

- Plan: `docs/plans/phase-2-trusted-data-auth-asset-plane.md`
- Scope: Phase 2 only — trusted data, authentication, private storage, resumable uploads, asset/reference foundations, and minimal Android/Web integrations.
- Start with: Task 1 — Close Phase 2 contracts and record ADRs.
- Execution rule: implement one task per coding session, run that task's Verify section, update this plan's Progress, then stop for review.
- Recommended first review checkpoint:
  - Inspect: OpenAPI diff, generated-client diff, ADR-0006, and ADR-0007.
  - Check: no existing resource was broken, every new operation has precise security/error semantics, and no Phase 3–9 API was pulled forward.
  - Accept when: contract lint/bundle/drift/mock checks pass and all three generated consumers agree.
  - Focus: contract ownership and long-lived security/storage decisions before persistence code begins.
