# Contract tooling

The contract toolchain is locked by `package.json`, `pnpm-lock.yaml`, and
`openapitools.json`:

- Node.js 24 and pnpm 10.34.5;
- Redocly CLI 2.54.2 for linting and bundling;
- Prism CLI 5.16.0 for contract mocks;
- OpenAPI Generator CLI wrapper 2.41.0 with generator 7.25.0;
- TypeScript 7.0.2 for generated Web client compilation.

Backend models use the `datamodel-code-generator` version locked in
`backend/uv.lock`.

Run from the repository root:

```powershell
corepack pnpm@10.34.5 install --dir contracts/tooling --frozen-lockfile
pwsh -File contracts/tooling/generate-contracts.ps1
pwsh -File contracts/tooling/check-generated.ps1
pwsh -File contracts/tooling/verify-additive-contract.ps1
pwsh -File contracts/tooling/verify-phase2-boundaries.ps1
pwsh -File contracts/tooling/verify-phase3-boundaries.ps1
pwsh -File contracts/tooling/verify-phase5-boundaries.ps1
pwsh -File contracts/tooling/verify-contract.ps1
pwsh -File contracts/tooling/compile-generated-kotlin.ps1
pwsh -File contracts/tooling/verify-generated.ps1
```

`generate-contracts.ps1` is the only supported regeneration entry point. It
updates the bundled contract and these generated targets:

- `backend/src/clothes_model/generated`;
- `android/core/api-contract/src/main/kotlin`;
- `web-admin/src/api/generated`.

Generated files and their directory README markers must not be edited manually.
`check-generated.ps1` regenerates into an isolated temporary directory and
compares SHA-256 manifests, making it suitable for the CI drift gate.

`verify-additive-contract.ps1` compares the current bundle with the committed
Phase 1 contract surface. It rejects removed paths, operations, response codes,
schemas, properties, required fields, enum values, or changed security on
existing operations. New Phase 2 paths and schemas remain allowed.

`verify-phase2-boundaries.ps1` asserts the authentication combinations,
declared problem statuses, and shared schemas for every Phase 2 auth, upload,
and asset operation.

`verify-phase5-boundaries.ps1` asserts the logical Comfy Provider versus
physical-node separation, immutable Workflow identity and lifecycle, redacted
node configuration, locked job snapshots, recovery states, examples, and Admin
security/idempotency boundaries.

`verify-contract.ps1`:

1. lints `contracts/openapi/openapi.yaml`;
2. resolves every `$ref` into `contracts/generated/openapi.yaml`;
3. runs the additive compatibility check;
4. checks the bundled contract for required V1 states and shared fields;
5. rejects V1.1 Outfit resources while allowing future-safe capability fields;
6. starts Prism and verifies configured examples with placeholder
   bearer/session/CSRF authentication values.

`verify-generated.ps1` runs the drift gate, Backend Pyright, Web TypeScript, and
standalone Kotlin compilation. Set `CLOTHES_MODEL_GRADLE` to override the
repository Gradle wrapper and `CLOTHES_MODEL_UV` when `uv` is not on `PATH`.
Its `-SkipKotlinCompile` switch is for split verification in restricted local
environments only; CI and the default command continue to run every gate.

The Kotlin generator normalization is intentionally narrow: it removes a
duplicate `ApiKeyAuth` import emitted for the two API-key security schemes and
maps free-form `Map<String, Any>` values to serializable `JsonElement` values.
This preserves the OpenAPI JSON boundary and is covered by regeneration drift.
