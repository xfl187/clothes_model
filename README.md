# Clothes Model

Private Android AI virtual try-on system with a fixed-server backend and a Web Admin control plane.

The repository has completed Phase 1–8. **Phase 4 — Minimum V1 End-to-End Vertical Slice** was verified by a credentialed operator run on 2026-09-27 against Volcengine Ark `doubao-seedream-4-5-251128` (Web Admin configured, validated, enabled and defaulted the Provider; Android uploaded one person and one garment and created one candidate; Ark executed it; the private output was persisted, survived a Backend restart, and displayed in Android). **Phase 5 — ComfyUI, Workflow Versioning and Recovery** is implementation-complete: logical Comfy Provider, singleton physical node, immutable Workflow versions, job-level Workflow locking, storage-paused recovery without resubmission, and CI/deployment gates; its deterministic exit gate passed 2026-09-28. **Phase 6 — Android V1 Completion** is complete: fixed `首页 / 素材 / 历史` navigation, reusable person/garment libraries with durable import recovery, the three-step precise-try-on wizard, truthful job/candidate/recovery/lineage states, the result gallery with comparison/favorite/download/share and deletion placeholders, and mask correction as a related new job, backed by a forward migration that enables private `mask` assets and mask-linked jobs. The deterministic exit gate is `android/verify-phase6.ps1`. By product-owner decision, real credentialed AutoDL/Comfy operator acceptance remains deferred until a real Workflow and node are prepared, and is mandatory before claiming Comfy production readiness. **Phase 7 — Web Admin and Operations Completion** is complete: the `概览 / 配置 / 运行维护` Web Admin IA with all A00–A12 pages, the Backend system-overview, retention/scan/cleanup, App Token rotation, and admin job-recovery surfaces, gated by `web-admin/verify-phase7.ps1`. **Phase 8 — V1 Hardening and Release Gate** is complete: the [V1 acceptance matrix](docs/acceptance/v1-acceptance-matrix.md), deterministic fault and security tests, consistent backup/restore tooling, operator [runbooks](docs/runbooks), and the aggregated `verify-phase8.ps1` release gate, with real credentialed AutoDL/Comfy acceptance remaining a documented manual release prerequisite. See the [Phase 4](docs/plans/phase-4-minimum-v1-e2e.md), [Phase 5](docs/plans/phase-5-comfyui-workflow-recovery.md), [Phase 6](docs/plans/phase-6-android-v1-completion.md), [Phase 7](docs/plans/phase-7-web-admin-operations-completion.md), and [Phase 8](docs/plans/phase-8-v1-hardening-release-gate.md) plans.


## Current scope

The completed foundation includes:

- a reproducible monorepo and shared OpenAPI/generated-client boundary;
- Backend, Android, Web Admin, CI, local-development, and deployment baselines;
- SQLite migrations, authentication/session security, encrypted secrets, private storage, resumable uploads, and assets/references;
- minimal Android connection/import recovery and Web Admin session foundations;
- the enforced V1 single-instance runtime constraint.

Phase 4 added the production Seedream adapter, synchronous paid-call safety, explicit paid validation, the minimum Admin Provider workflow, and the Android select/upload/create/poll/recover/result flow. Ordinary verification uses injected transports and never spends Provider credits. Result zoom/save/share, the materials library and history, the results grid, and mask correction were delivered in Phase 6.

## Sources of truth

- Product behavior: [Product Spec](docs/superpowers/specs/2026-09-23-android-virtual-try-on-design.md)
- Confirmed behavior flows: [Product Flow](docs/product-flow.md)
- Phase boundaries: [Implementation Roadmap](docs/roadmap/implementation-roadmap.md)
- Completed implementation evidence: [Phase 4 Implementation Plan](docs/plans/phase-4-minimum-v1-e2e.md)
- Completed implementation plans: [Phase 5](docs/plans/phase-5-comfyui-workflow-recovery.md), [Phase 6 Android V1 Completion](docs/plans/phase-6-android-v1-completion.md), [Phase 7 Web Admin and Operations Completion](docs/plans/phase-7-web-admin-operations-completion.md), [Phase 8 V1 Hardening and Release Gate](docs/plans/phase-8-v1-hardening-release-gate.md), the cross-cutting [Local-first Asset Library](docs/plans/local-first-asset-library.md) (Backend migration `20260929_0006`, owner scopes, and opt-in 24-hour input-binary cleanup; follow its rollout order and keep cleanup disabled until migrated content is acknowledged on device), and the [Provider Archive Lifecycle](docs/plans/provider-archive-lifecycle.md)
- Current implementation plan: none — Phase 8 complete; V1 release candidate gated by `verify-phase8.ps1`, pending the deferred credentialed AutoDL/Comfy acceptance before claiming Comfy production readiness
- UI behavior: the Android and Web Admin UI Specs under `docs/superpowers/specs/`
- Visual language: [DESIGN.md](DESIGN.md)
- Long-lived technical decisions: [Architecture Decision Records](docs/adr/README.md)

When these artifacts differ, use the authority order recorded in the Phase Plan; do not silently reinterpret product behavior to match implementation convenience.

## Repository ownership

| Path | Responsibility | Planned owner task |
|---|---|---|
| `backend/` | FastAPI modular-monolith application, database infrastructure, scheduler boundary, and backend tests | Tasks 3–4 |
| `android/` | Native Kotlin/Compose application and generated contract client module | Task 7 |
| `web-admin/` | React/TypeScript Web Admin application | Task 6 |
| `contracts/` | Canonical OpenAPI source, examples, tooling, mock configuration, and generated artifacts | Tasks 2 and 5 |
| `infra/` | Local Compose, production container, Caddy, volumes, and deployment entrypoints | Task 8 |
| `docs/adr/` | Accepted architecture decisions and later explicit superseding decisions | Task 1 onward |
| `.github/workflows/` | CI quality gates | Task 9 |
| `docs/`, `prototypes/`, `DESIGN.md` | Confirmed product, design, planning, and prototype inputs | Preserved project memory |

Phases 1–7 are complete. Jobs, the Seedream Provider, Comfy/Workflow persistence, the full Android V1 product surface, and the Web Admin control plane (overview, Comfy node, Workflows, LLM Provider, default backend, diagnostics, storage retention/scan/cleanup, and App Token rotation) are real behavior. Phase 8 addresses V1 hardening and the release gate.

## Repository policies

- Commit all dependency lockfiles: `uv.lock`, `pnpm-lock.yaml`, and Gradle wrapper/version catalog inputs.
- Do not use dynamic dependency versions in production builds.
- Commit deterministic generated API artifacts, mark them as generated, and never edit them by hand.
- Task 5 must provide regeneration and drift checks for generated contract code.
- Never commit `.env`, credentials, signing material, databases, uploaded images, private storage, build output, IDE state, or local worktrees.
- `.env.example` may contain names and non-secret placeholders only.
- Existing prototype content under `.superpowers/brainstorm/**/content/` is project input and remains trackable; runtime token, port, state, and execution-ledger files are ignored.

## Local development matrix

Use Docker Desktop with Linux containers for the contract mock, containerized Backend, and production-shaped deployment. Web and Android can also run from their pinned local toolchains.

| Surface | Command | Host endpoint | Purpose |
|---|---|---|---|
| Contract mock | `docker compose -f infra/compose.yaml --profile contract up --build contract-mock` | `http://localhost:4010` | Shared OpenAPI mock for Web and Android skeletons |
| Backend | `./infra/start-development.ps1` | `http://localhost:18000` | Containerized Backend with the local ignored `.env`, encrypted Provider secrets, and one explicitly owned scheduler |
| Web Admin | `corepack pnpm --filter @clothes-model/web-admin dev` | `http://localhost:5173` | Vite shell; `/api` is proxied to the contract mock on port 4010 |
| Android emulator | `android\gradlew.bat -p android :app:installDebug` | mock base URL `http://10.0.2.2:4010` | Installs the Android engineering shell against the host mock |
| Production shape | `$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY='<local-secret>'; docker compose -f infra/compose.yaml --profile production up --build` | `https://localhost:8443` | Caddy TLS proxy in front of one application deployment unit |

The production profile also listens on `http://localhost:8080` for the Caddy HTTPS redirect. Caddy uses its local development CA, so command-line smoke tests must trust that CA or deliberately opt out of certificate validation for localhost only.

## V1 deployment constraints

- `app` is fixed to one Compose replica and one Uvicorn worker.
- The scheduler runs in that application process and acquires the persistent instance lock; a second scheduler owner must fail closed.
- The application image builds Web Admin in a Node stage and serves the resulting static shell from the Backend process.
- Startup runs the committed Alembic migrations before Uvicorn.
- SQLite, private storage, and scheduler lock state use separate named volumes.
- The encryption key crosses the deployment boundary as a read-only Compose secret sourced from the host environment. Never place its value in `.env.example` or source control.
- The production profile contains only `app` and `caddy`; the contract mock is opt-in and cannot start as part of production.

Copy `.env.example` to a local, ignored `.env` only for non-secret configuration. Inject secrets from the host or deployment platform.

See [infra/README.md](infra/README.md) for profile-specific operations and verification commands.

## CI quality gates

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs five independent quality boundaries:

- `Contract` installs locked tooling, regenerates into a temporary directory, rejects generated drift, and compiles all three contract consumers.
- `Backend`, `Web Admin`, and `Android` run in parallel with locked installs, lint/static analysis, tests, and clean builds.
- `Deployment smoke` starts only after the three application build jobs succeed, clean-builds the container images, and probes Backend readiness and the Web shell through Caddy HTTPS.

Every job records runtime and dependency-tool versions. Test reports and build logs are retained for 14 days; generated workspaces, credentials, private data, and runtime volumes are never uploaded. Superseded runs on the same branch or pull request are cancelled automatically.

For protected `main` branches, configure these workflow checks as required: `Contract`, `Backend`, `Web Admin`, `Android`, and `Deployment smoke`. That repository setting is what turns any contract drift, lint, type, test, build, or deployment failure into a merge block.

Run the same primary gates locally before opening a pull request:

```powershell
./contracts/tooling/verify-generated.ps1
Push-Location backend; uv sync --locked; uv run ruff check .; uv run pyright; uv run pytest; uv build; Pop-Location
corepack pnpm@10.34.5 install --frozen-lockfile
corepack pnpm@10.34.5 web:lint
corepack pnpm@10.34.5 web:typecheck
corepack pnpm@10.34.5 web:test
corepack pnpm@10.34.5 web:build
android/gradlew.bat -p android --no-daemon :core:api-contract:compileKotlin :app:assembleDebug :app:lintDebug :app:testDebugUnitTest :app:assembleDebugAndroidTest :app:assembleRelease
./android/verify-release-boundary.ps1
```
## Phase 1 exit verification

The integrated Phase 1 gate was last run on 2026-09-26 from an isolated source
snapshot containing only files selected by Git ignore rules. No local `.env`,
dependency directory, build output, database, upload, or IDE state was copied
into that snapshot.

Prerequisites are the versions pinned by the repository and CI:

- Node.js 24 and pnpm 10.34.5 through Corepack;
- Python 3.14.7 and uv 0.12.18;
- JDK 17, Gradle wrapper 9.4.1, Android SDK 37, and build-tools 36.0.0;
- Docker with Compose v2-compatible commands;
- Playwright Chromium for the browser smoke test.

Set `ANDROID_HOME`/`ANDROID_SDK_ROOT`, or create an ignored
`android/local.properties` containing `sdk.dir`. Keep machine-specific SDK paths
out of source control. `uv` may be placed on `PATH`; contract scripts also accept
an explicit executable through `CLOTHES_MODEL_UV`. The Gradle wrapper remains the
canonical Gradle entry point.

Run the clean gate from the repository root:

```powershell
corepack pnpm@10.34.5 install --frozen-lockfile
corepack pnpm@10.34.5 --filter @clothes-model/web-admin exec playwright install chromium

./contracts/tooling/verify-generated.ps1

Push-Location backend
uv sync --locked
uv run ruff check .
uv run pyright
uv run pytest
uv build
Pop-Location

corepack pnpm@10.34.5 web:lint
corepack pnpm@10.34.5 web:typecheck
corepack pnpm@10.34.5 web:test
corepack pnpm@10.34.5 web:build
corepack pnpm@10.34.5 --filter @clothes-model/web-admin check:bundle
corepack pnpm@10.34.5 web:test:e2e

android/gradlew.bat -p android --no-daemon clean `
  :core:api-contract:compileKotlin `
  :app:assembleDebug `
  :app:lintDebug `
  :app:testDebugUnitTest `
  :app:assembleDebugAndroidTest `
  :app:assembleRelease
./android/verify-release-boundary.ps1
```

Run the production-shaped gate with a disposable local secret:

```powershell
$env:CLOTHES_MODEL_ENCRYPTION_MASTER_KEY='phase1-local-verification-only'
docker compose -f infra/compose.yaml --profile contract --profile production build --no-cache contract-mock app
docker compose -f infra/compose.yaml --profile production up -d --no-build
curl.exe --fail --insecure https://localhost:8443/health/ready
curl.exe --fail --insecure https://localhost:8443/
docker compose -f infra/compose.yaml --profile production down --remove-orphans
```

The 2026-09-26 local run used these environment-only adaptations:

- JDK 21 was installed locally; CI remains the authoritative JDK 17 build.
- Windows reserved ports 8080/8443, so the Compose-supported overrides 18080
  and 18443 were used. Repository defaults remain unchanged.
- The official Gradle distribution endpoint reset locally; the same Gradle
  9.4.1 archive was obtained from a mirror and accepted only after its SHA-256
  matched the wrapper checksum. CI continues to use the official wrapper URL.
- `corepack enable` could not update the protected Node installation directory;
  invoking the pinned `corepack pnpm@10.34.5` directly succeeded.
- The repository has no Git remote yet, so a hosted empty-cache GitHub Actions
  run and branch-protection settings cannot be observed locally. All equivalent
  locked installs, clean builds, tests, generation checks, and deployment smoke
  checks passed.
