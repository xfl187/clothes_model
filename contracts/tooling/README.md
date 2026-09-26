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
powershell -ExecutionPolicy Bypass -File contracts/tooling/generate-contracts.ps1
powershell -ExecutionPolicy Bypass -File contracts/tooling/check-generated.ps1
powershell -ExecutionPolicy Bypass -File contracts/tooling/verify-contract.ps1
powershell -ExecutionPolicy Bypass -File contracts/tooling/verify-generated.ps1
```

`generate-contracts.ps1` is the only supported regeneration entry point. It
updates the bundled contract and these generated targets:

- `backend/src/clothes_model/generated`;
- `android/core/api-contract/src/main/kotlin`;
- `web-admin/src/api/generated`.

Generated files and their directory README markers must not be edited manually.
`check-generated.ps1` regenerates into an isolated temporary directory and
compares SHA-256 manifests, making it suitable for the Task 9 CI drift gate.

`verify-contract.ps1`:

1. lints `contracts/openapi/openapi.yaml`;
2. resolves every `$ref` into `contracts/generated/openapi.yaml`;
3. checks the bundled contract for required V1 states and shared fields;
4. rejects V1.1 Outfit resources while allowing future-safe capability fields;
5. starts Prism and verifies Job, Provider Capabilities, Storage, and Diagnostics
   examples with placeholder bearer/session/CSRF authentication values.

`verify-generated.ps1` runs the drift gate, Backend Pyright, Web TypeScript, and
standalone Kotlin compilation. Until Task 7 provides the repository Gradle
wrapper, set `CLOTHES_MODEL_GRADLE` to a Gradle 8.13+ executable. Set
`CLOTHES_MODEL_UV` when `uv` is not on `PATH`.

The Kotlin generator normalization is intentionally narrow: it removes a
duplicate `ApiKeyAuth` import emitted for the two API-key security schemes and
maps free-form `Map<String, Any>` values to serializable `JsonElement` values.
This preserves the OpenAPI JSON boundary and is covered by regeneration drift.
