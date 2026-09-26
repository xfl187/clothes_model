# ADR-0001: Monorepo and toolchains

- Status: Accepted
- Date: 2026-09-24

## Context

The product consists of a Backend, an Android application, a Web Admin application, shared API contracts, and deployment infrastructure. One maintainer must be able to change a contract and all consumers atomically. The repository starts without an existing build or dependency-management baseline.

## Decision

Use one Git monorepo with these ownership boundaries:

- `backend/` for the Python/FastAPI application;
- `android/` for the Kotlin/Compose application;
- `web-admin/` for the React/TypeScript application;
- `contracts/` for canonical OpenAPI sources, mock inputs, tooling, and generated artifacts;
- `infra/` for local and V1 deployment infrastructure;
- `docs/adr/` for architecture decisions.

Use ecosystem-native dependency management:

- Backend: Python 3.14, `uv`, `pyproject.toml`, and committed `uv.lock`;
- Web and JavaScript contract tooling: Node.js 24 LTS, pnpm 10, and committed `pnpm-lock.yaml`;
- Android: JDK 17, Gradle wrapper, Kotlin DSL, and a committed version catalog.

Dependency declarations use compatible stable ranges where appropriate; lockfiles and the Gradle wrapper make builds reproducible. Dynamic production dependency versions are prohibited.

Deterministically generated API artifacts are committed so each platform can build without installing every other platform's generator toolchain. Generated files must carry a generated marker, must not be edited manually, and must pass regeneration drift checks in CI.

Environment files, secrets, signing material, databases, uploaded files, private storage, build outputs, IDE state, local worktrees, and transient execution state are not tracked.

## Consequences

- Contract and consumer changes can be reviewed in one commit.
- CI can validate all three applications against the same contract.
- The repository contains multiple build systems, but does not add a cross-language build orchestrator during Phase 1.
- Generated-code diffs are accepted in exchange for clean, independent platform builds; CI is responsible for proving reproducibility.
